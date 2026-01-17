import json
import asyncio
import logging
from typing import Dict, Optional, List
from urllib import request
from utils import current_timestamp_s
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
import redis.asyncio as redis
from config import settings
from models import DeviceInfo, DriftMessage
from models import (
    DriftEvent, DriftMsgType, DeviceStatus
)


logger = logging.getLogger(__name__)

'''
设备WebSocket连接管理器类
'''
class ConnectionManager:
    # 构造函数
    def __init__(self):
        # 活跃连接
        self._connections: Dict[str, WebSocket] = {}
        # 设备状态
        self._device_status: Dict[str, DeviceStatus] = {}
        # Redis客户端
        self._redis_client = None
        
    # 连接redis缓存
    async def connect_redis(self):
        """连接 Redis"""
        try:
            self._redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            await self._redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self._redis_client = None
    
    # 断开redis缓存
    async def disconnect_redis(self):
        """断开 Redis 连接"""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None
            logger.info("Redis 连接已断开")

    # TODO：使用Redis过期时间来监控心跳
    async def start_heartbeat_monitor(self):
        """启动心跳监控"""
        return asyncio.create_task(
            self._monitor_heartbeats()
        )
    
    # 监控心跳
    async def _monitor_heartbeats(self):
        logger.info("心跳监控已启动")

        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            now_ts = current_timestamp_s()
            timeout_devices = []

            for device_id in self._connections.keys():
                request = DriftMessage(
                    type=DriftMsgType.S2D_CONTROL,
                    event=DriftEvent.DEVICE_INFO,
                    deviceId=device_id,
                    playId=device_id,
                )
                await self.send_message(device_id, request.model_dump())

                time_diff = now_ts - self._device_status[device_id].last_heartbeat
                if time_diff > settings.heartbeat_timeout:
                    logger.warning(f"设备 {device_id} 心跳超时")
                    timeout_devices.append(device_id)
            
            # 断开超时设备
            for device_id in timeout_devices:
                await self.disconnect(device_id, code=1008, reason="心跳超时")
    
    # 接受设备连接
    async def connect(
        self,
        websocket: WebSocket,
        room_id: str,
        device_sn: str,
        device_id: str,
        language: str
        ) -> str:
        """设备连接"""
        await websocket.accept()
        
        # 保存连接
        self._connections[device_id] = websocket
        
        # 初始化设备状态
        device_info = DeviceInfo(
            no=device_sn,
        )

        # 保存设备状态
        self._device_status[device_id] = DeviceStatus(
            device_id=device_id,
            device_info=device_info,
        )
        
        logger.info(f"设备建立连接: {device_id}")
        
    
    # 断开设备连接
    async def disconnect(
        self,
        device_id: str,
        code: int = 1000,
        reason: str = "正常关闭"
        ):
        """断开连接"""
        if device_id in self._connections:
            try:
                websocket = self._connections[device_id]
                # 检查连接状态
                if websocket.client_state != WebSocketState.DISCONNECTED and websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.close(code=code, reason=reason)
            except Exception as e:
                logger.error(f"关闭连接时出错: {e}")
            finally:
                # 清理连接
                self._cleanup_connection(device_id)

    # 清理连接数据
    def _cleanup_connection(self, device_id: str):
        """清理连接数据（从活跃连接、设备状态和房间映射中移除）"""
        if device_id in self._connections:
            del self._connections[device_id]
        
        if device_id in self._device_status:
            del self._device_status[device_id]
        
        logger.info(f"连接清理完成: {device_id}")
    
    # 心跳监控
    async def update_heartbeat(self, device_id: str):
        """更新心跳时间"""
        if device_id in self._device_status:
            self._device_status[device_id].last_heartbeat = current_timestamp_s()
        else:
            logger.error(f"更新心跳时间失败：设备连接 {device_id} 不存在")
    
    # 接收设备消息
    async def receive_message(self, device_id: str):
        """接收设备消息"""
        message_data = None
        if device_id in self._connections:
            websocket = self._connections[device_id]
            message_data = await websocket.receive_json()
            logger.debug(f"收到消息: {json.dumps(message_data, indent=2, ensure_ascii=False)}")
        return message_data

    # 发送消息到指定设备
    async def send_message(self, device_id: str, message: dict):
        logger.debug(f"发送消息: {json.dumps(message, indent=2, ensure_ascii=False)}")
        if device_id in self._connections:
            websocket = self._connections[device_id]
            await websocket.send_json(message)
    
    # 获取设备信息
    def get_device_status(self, device_id: str) -> Optional[DeviceStatus]:
        """获取设备信息"""
        return self._device_status.get(device_id)
    
    # 检查设备是否已连接
    def connected(self, device_id: str) -> bool:
        """检查设备是否已连接"""
        return device_id in self._connections
    
    def get_device_list(self) -> List[DeviceStatus]:
        """获取所有活跃连接"""
        return list(self._device_status.keys())
    
    # 更新设备信息
    def update_device_info(self, device_id: str, device_info: DeviceInfo):
        """更新设备信息"""
        if device_id in self._device_status:
            self._device_status[device_id].device_info = device_info
        else:
            logger.error(f"更新设备信息失败：设备连接 {device_id} 不存在")


# 全局连接管理器
connectionManager = ConnectionManager()
