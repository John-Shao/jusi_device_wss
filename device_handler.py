import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import WebSocket

from models import (
    BaseMessage, DeviceInfoMessage, GetRtmpMessage, GetScreenMessage,
    HeartbeatMessage, DeviceJoinMessage, EventType, MessageType, DeviceInfo
)
from manager import manager
from config import settings
from auth_handler import authenticate_device
import file_uploader


logger = logging.getLogger(__name__)

class DeviceMessageHandler:
    """设备消息处理器"""
    
    @staticmethod
    async def handle_message(
        message_data: dict,
        connection_id: str,
        websocket: WebSocket
        ) -> Optional[dict]:
        """处理设备消息"""
        try:
            # 验证消息格式
            message = BaseMessage(**message_data)
            
            # 根据消息类型处理
            if message.type == MessageType.NOTIFY:
                return await DeviceMessageHandler._handle_notify(
                    message, connection_id, websocket
                )
            elif message.type == MessageType.DEVICE_CONTROL:
                return await DeviceMessageHandler._handle_device_control(
                    message, connection_id, websocket
                )
            else:
                return {
                    "type": "message",
                    "code": -1,
                    "error_msg": f"不支持的消息类型: {message.type}"
                }
                
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            return {
                "type": "message",
                "code": -1,
                "error_msg": f"消息格式错误: {str(e)}"
            }
    
    @staticmethod
    async def _handle_notify(
        message: BaseMessage,
        connection_id: str,
        websocket: WebSocket
        ) -> Optional[dict]:
        """处理 notify 类型消息"""
        
        # 更新心跳时间
        await manager.update_heartbeat(connection_id)
        
        if message.event == EventType.JOIN:
            # 心跳消息
            logger.debug(f"收到心跳: {connection_id}")
            return None  # 心跳不需要响应
            
        elif message.event == EventType.DEVICE_INFO:
            # 设备信息上报
            return await DeviceMessageHandler._handle_device_info(
                message, connection_id
            )
        else:
            if message.code:
                message = f"设备 {connection_id} 处理 {message.event} 指令失败，错误码: {message.code}"
                logger.warning(message)
            else:
                message = f"设备 {connection_id} 处理 {message.event} 指令成功"
                logger.info(message)
            return None  # 其他通知不需要响应
    
    @staticmethod
    async def _handle_device_control(
        message: BaseMessage,
        connection_id: str,
        websocket: WebSocket
    ) -> Optional[dict]:
        """处理 device_control 类型消息"""
        
        if message.event == EventType.GET_RTMP:
            # 获取 RTMP 地址
            return await DeviceMessageHandler._get_rtmp_address(
                message, connection_id
            )
            
        elif message.event == EventType.GET_SCREEN:
            # 获取截图地址
            return await DeviceMessageHandler._get_screen_address(
                message, connection_id
            )
            
        elif message.event == EventType.POWER_OFF:
            # 关机请求
            return await DeviceMessageHandler._handle_power_off(
                message, connection_id
            )
            
        else:
            logger.warning(f"未知的 device_control 事件: {message.event}")
            return {
                "type": "message",
                "code": -1,
                "error_msg": f"未知事件: {message.event}"
            }
    
    @staticmethod
    async def _handle_device_info(
        message: BaseMessage,
        connection_id: str
    ) -> dict:
        """处理设备信息上报"""
        try:
            # 解析设备信息
            device_info_data = message.data
            if not device_info_data:
                raise ValueError("设备信息不能为空")
            
            device_info = DeviceInfo(**device_info_data)
            
            # 更新管理器中的设备信息
            manager.update_device_info(connection_id, device_info)
            
            logger.info(f"设备信息更新: {connection_id}")
            
            return {
                "type": "notify",
                "event": "device_info",
                "code": 0,
                "playId": message.playId,
                "deviceId": message.deviceId
            }
            
        except Exception as e:
            logger.error(f"处理设备信息时出错: {e}")
            return {
                "type": "device_notify",
                "event": "device_info",
                "code": -1,
                "playId": message.playId,
                "deviceId": message.deviceId,
                "error_msg": str(e)
            }
    
    @staticmethod
    async def _get_rtmp_address(
        message: BaseMessage,
        connection_id: str
    ) -> dict:
        """处理获取 RTMP 地址请求"""
        try:
            # 获取设备状态
            device_status = manager.device_status.get(connection_id)
            if not device_status:
                raise ValueError("设备未连接")
            
            # 生成 RTMP 地址（这里使用配置的服务器地址）
            stream_id = f"{device_status.device_sn}_{device_status.device_id}"
            rtmp_url = f"rtmp://{settings.VIDEO_RTMP_HOST}:{settings.VIDEO_RTMP_PORT}/live/{stream_id}"
            
            # 获取设备信息中的分辨率等设置
            device_info = manager.get_device_info(connection_id)
            
            return {
                "type": "device_notify",
                "event": "get_rtmp",
                "deviceId": message.deviceId,
                "code": 0,
                "data": {
                    "rtmp_url": rtmp_url,
                    "stream_res": device_info.stream_res if device_info else "720P",
                    "stream_bitrate": device_info.stream_bitrate if device_info else 2000000,
                    "stream_framerate": device_info.stream_framerate if device_info else 30
                }
            }
            
        except Exception as e:
            logger.error(f"生成RTMP地址时出错: {e}")
            return {
                "type": "device_notify",
                "event": "get_rtmp",
                "deviceId": message.deviceId,
                "code": -1,
                "error_msg": str(e)
            }
    
    @staticmethod
    async def _get_screen_address(
        message: BaseMessage,
        connection_id: str
    ) -> dict:
        """处理获取截图地址请求"""
        try:
            device_status = manager.device_status.get(connection_id)
            if not device_status:
                raise ValueError("设备未连接")
            
            # 这里应该返回实际的上传地址
            # 示例中使用一个固定的上传端点
            upload_url = f"https://{settings.HOST}/api/upload/screenshot"
            
            return {
                "type": "device_notify",
                "event": "get_screen",
                "deviceId": message.deviceId,
                "code": 0,
                "data": {
                    "screenName": "",
                    "deviceId": message.deviceId,
                    "url": upload_url,
                    "roomId": device_status.room_id,
                    "fileBase64": ""
                }
            }
            
        except Exception as e:
            logger.error(f"生成截图地址时出错: {e}")
            return {
                "type": "device_notify",
                "event": "get_screen",
                "deviceId": message.deviceId,
                "code": -1,
                "error_msg": str(e)
            }
    
    @staticmethod
    async def _handle_power_off(
        message: BaseMessage,
        connection_id: str
    ) -> dict:
        """处理关机请求"""
        try:
            # 这里可以添加关机前的清理逻辑
            
            logger.info(f"设备请求关机: {connection_id}")
            
            return {
                "type": "device_notify",
                "event": "power_off",
                "deviceId": message.deviceId,
                "code": 0,
                "data": {"status": "shutting_down"}
            }
            
        except Exception as e:
            logger.error(f"处理关机请求时出错: {e}")
            return {
                "type": "device_notify",
                "event": "power_off",
                "deviceId": message.deviceId,
                "code": -1,
                "error_msg": str(e)
            }
    
    @staticmethod
    async def handle_screenshot_upload(
        upload_data: dict,
        connection_id: str
    ) -> dict:
        """处理截图上传"""
        try:
            # 验证上传数据
            required_fields = ["screenName", "deviceId", "url", "roomId", "fileBase64"]
            for field in required_fields:
                if field not in upload_data:
                    raise ValueError(f"缺少必要字段: {field}")
            
            # 上传截图
            result = await file_uploader.upload_screenshot(upload_data)
            
            return {
                "code": 0,
                "message": "截图上传成功",
                "data": result
            }
            
        except Exception as e:
            logger.error(f"上传截图时出错: {e}")
            return {
                "code": -1,
                "error_msg": str(e)
            }