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
    ControlMessage, EventType, MessageType
)


logger = logging.getLogger(__name__)

'''
设备状态信息类
'''
class DeviceStatus:
    """设备状态"""
    
    def __init__(
        self,
        room_id: str,
        device_sn: str,
        device_id: str,
        connection_time: datetime,
        last_heartbeat: datetime
        ):
        
        self.room_id = room_id
        self.device_sn = device_sn
        self.device_id = device_id
        self.connection_time = connection_time  # 连接时间
        self.last_heartbeat = last_heartbeat  # 最后心跳时间
        self.device_info: Optional[DeviceInfo] = None  # 设备信息
        self.video_pushing = False  # 是否正在推流
        self.audio_pulling = False  # 是否正在拉流
        self.recording = False  # 是否正在录像
        self.rtmp_url: Optional[str] = None  # RTMP 推流地址
        self.rtsp_url: Optional[str] = None  # RTSP 拉流地址

'''
设备连接管理器类
'''
class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 活跃连接
        self.active_connections: Dict[str, WebSocket] = {}
        # 设备状态
        self.device_status: Dict[str, DeviceStatus] = {}
        # 房间-设备映射
        self.room_devices: Dict[str, Set[str]] = {}
        # Redis 客户端
        self.redis_client = None
        # 心跳监控任务
        self.heartbeat_monitor_task = None
    
    # 连接缓存
    async def connect_redis(self):
        """连接 Redis"""
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.error(f"Redis 连接失败: {e}")
            self.redis_client = None
    
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
                    if time_diff > timedelta(seconds=settings.HEARTBEAT_TIMEOUT):
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
        device_id: str
        ) -> str:
        """设备连接"""
        await websocket.accept()
        
        # 生成连接ID
        connection_id = f"{room_id}:{device_sn}:{device_id}"
        
        # 保存连接
        self.active_connections[connection_id] = websocket
        
        # 初始化设备状态
        self.device_status[connection_id] = DeviceStatus(
            room_id=room_id,
            device_sn=device_sn,
            device_id=device_id,
            connection_time=datetime.now(),
            last_heartbeat=datetime.now()
        )
        
        # 更新"房间-设备"映射
        if room_id not in self.room_devices:
            self.room_devices[room_id] = set()

        self.room_devices[room_id].add(connection_id)
        
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
            # 从房间映射中移除
            status = self.device_status[connection_id]
            if status.room_id in self.room_devices:
                self.room_devices[status.room_id].discard(connection_id)
            
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
        logger.debug(f"发送消息: {json.dumps(message, indent=2)}")
        if connection_id in self.active_connections:
            try:
                websocket = self.active_connections[connection_id]
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"发送消息失败: {e}")
                await self.disconnect(connection_id)
        return False
    
    # 广播消息
    async def broadcast_to_room(self, room_id: str, message: dict):
        """广播消息到房间所有设备"""
        if room_id in self.room_devices:
            for connection_id in list(self.room_devices[room_id]):
                await self.send_message(connection_id, message)
    
    # 获取设备连接
    async def get_device_connection(self, device_id: str) -> Optional[str]:
        """根据设备ID获取连接ID"""
        for connection_id, status in self.device_status.items():
            if status.device_id == device_id:
                return connection_id
        return None
    
    # 获取设备信息
    def get_device_info(self, connection_id: str) -> Optional[DeviceInfo]:
        """获取设备信息"""
        if connection_id in self.device_status:
            return self.device_status[connection_id].device_info
        return None
    
    # 更新设备信息
    def update_device_info(self, connection_id: str, device_info: DeviceInfo):
        """更新设备信息"""
        if connection_id in self.device_status:
            self.device_status[connection_id].device_info = device_info
    
    # 获取在线设备列表
    def get_online_devices(self, room_id: Optional[str] = None) -> List[str]:
        """获取在线设备列表"""
        devices = []
        for connection_id, status in self.device_status.items():
            if not room_id or status.room_id == room_id:
                devices.append({
                    "device_id": status.device_id,
                    "device_sn": status.device_sn,
                    "room_id": status.room_id,
                    "connected_at": status.connection_time.isoformat(),
                    "last_heartbeat": status.last_heartbeat.isoformat()
                })
        return devices

'''
全局连接管理器
'''
manager = ConnectionManager()
