import json
import asyncio
import logging
from typing import Dict, Set, Optional, List
from datetime import datetime, timedelta
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
import redis.asyncio as redis
from config import settings
from models import DeviceInfo
from models import (
    EventType, MessageType, DeviceStatus
)


logger = logging.getLogger(__name__)

'''
设备WebSocket连接管理器类
'''
class ConnectionManager:
    # 构造函数
    def __init__(self):
        # 活跃连接
        self.active_connections: Dict[str, WebSocket] = {}
        # 设备状态
        self.device_status: Dict[str, DeviceStatus] = {}
        # Redis客户端
        self.redis_client = None
        # 心跳监控任务
        self.heartbeat_monitor_task = None
        # 连接redis缓存
        self.connect_redis()

    def __del__(self):
        """析构函数"""
        # 断开redis缓存
        self.disconnect_redis()
        # 取消心跳监控任务
        if self.heartbeat_monitor_task:
            self.heartbeat_monitor_task.cancel()
        
    # 连接redis缓存
    async def connect_redis(self):
        """连接 Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self.redis_client = None
    
    # 断开redis缓存
    async def disconnect_redis(self):
        """断开 Redis 连接"""
        if self.redis_client:
            await self.redis_client.close()
            self.redis_client = None
            logger.info("Redis 连接已断开")

    async def start_heartbeat_monitor(self):
        """启动心跳监控"""
        self.heartbeat_monitor_task = asyncio.create_task(
            self._monitor_heartbeats()
        )
    
    # 监控心跳
    async def _monitor_heartbeats(self):
        """监控心跳"""
        while True:
            await asyncio.sleep(60)  # 每分钟检查一次
            
            now = datetime.now()
            timeout_devices = []
            
            for device_id, status in list(self.device_status.items()):
                if status.last_heartbeat:
                    time_diff = now - status.last_heartbeat
                    if time_diff > timedelta(seconds=settings.heartbeat_timeout):
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
        
        # 生成连接ID
        connection_id = device_id
        
        # 保存连接
        self.active_connections[connection_id] = websocket
        
        # 初始化设备状态
        device_info = DeviceInfo(
            no=device_sn,
        )

        # 保存设备状态
        self.device_status[connection_id] = DeviceStatus(
            device_id=device_id,
            device_info=device_info,
            connection_time=datetime.now(),
            last_heartbeat=datetime.now(),
        )
        
        logger.info(f"设备连接: {connection_id}")
        
        # 发送连接确认
        await self.send_message(
            connection_id,
            {
                "code": 0,
                "type": MessageType.NOTIFY,
                "event": EventType.DEVICE_JOIN,
                "data": {}
            }
        )
        return connection_id
    
    # 断开设备连接
    async def disconnect(
        self,
        connection_id: str,
        code: int = 1000,
        reason: str = "正常关闭"
        ):
        """断开连接"""
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                # 检查连接状态
                if websocket.client_state != WebSocketState.DISCONNECTED and websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.close(code=code, reason=reason)
            except Exception as e:
                logger.error(f"关闭连接时出错: {e}")
            finally:
                # 清理连接
                self._cleanup_connection(connection_id)

    # 清理连接数据
    def _cleanup_connection(self, connection_id: str):
        """清理连接数据（从活跃连接、设备状态和房间映射中移除）"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if connection_id in self.device_status:
            del self.device_status[connection_id]
        
        logger.info(f"连接清理完成: {connection_id}")
    
    # 心跳监控
    async def update_heartbeat(self, connection_id: str):
        """更新心跳时间"""
        if connection_id in self.device_status:
            self.device_status[connection_id].last_heartbeat = datetime.now()
    
    # 发送消息
    async def send_message(self, connection_id: str, message: dict):
        """发送消息到指定连接"""
        logger.debug(f"发送消息: {json.dumps(message, indent=2, ensure_ascii=False)}")
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                await self.disconnect(connection_id)
    
    # 获取设备信息
    def get_device_info(self, connection_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        return self.device_status[connection_id].device_info if connection_id in self.device_status else None
    
    # 更新设备信息
    def update_device_info(self, connection_id: str, device_info: DeviceInfo):
        """更新设备信息"""
        if connection_id in self.device_status:
            self.device_status[connection_id].device_info = device_info
        else:
            logger.error(f"更新设备信息失败：设备连接 {connection_id} 不存在")


# 全局连接管理器
connectionManager = ConnectionManager()
