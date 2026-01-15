import logging
from typing import Optional
from unittest.mock import Base
from fastapi import WebSocket
from py import log

from models import (
    BaseMessage, EventType, MessageType, DeviceInfo
)
from connection_manager import connectionManager
from config import settings
import file_uploader


logger = logging.getLogger(__name__)

# 处理设备发送的消息
async def handle_device_message(
    message_data: dict,
    connection_id: str,
    websocket: WebSocket
    ) -> Optional[dict]:
    """处理设备消息"""
    try:
        # 验证消息格式
        message = BaseMessage(**message_data)
        
        # 根据消息类型处理
        if message.type == MessageType.D2S_NOTIFY:
            return await handle_notify_message(
                message, connection_id, websocket
            )
        elif message.type == MessageType.D2S_DEVICE_CONTROL:
            return await handle_device_control(
                message, connection_id, websocket
            )
        else:
            logger.warning(f"不支持的消息类型: {message.type}")
            err_msg = BaseMessage(
                type=MessageType.S2D_MESSAGE,
                event=message.event,
                deviceId=message.deviceId,
                playId=message.playId,
                code=-1,
            )
            return err_msg.model_dump()
            
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        err_msg = BaseMessage(
                type=MessageType.S2D_MESSAGE,
                event=message.event,
                deviceId=message.deviceId,
                playId=message.playId,
                code=-1,
            )
        return err_msg.model_dump()


# 处理 notify 类型消息
async def handle_notify_message(
    message: BaseMessage,
    connection_id: str,
    websocket: WebSocket
    ) -> Optional[dict]:
    # 更新心跳时间
    await connectionManager.update_heartbeat(connection_id)
    
    if message.event == EventType.JOIN:
        logger.debug(f"收到心跳: {connection_id}")
        return None  # 心跳不需要响应
        
    elif message.event == EventType.DEVICE_INFO:
        # 设备信息上报
        return await handle_device_info(
            message, connection_id
        )
    else:
        # 系统控制（control）结果通知
        if message.code:
            message = f"设备 {connection_id} 处理 {message.event} 指令失败，错误码: {message.code}"
            logger.warning(message)
        else:
            message = f"设备 {connection_id} 处理 {message.event} 指令成功"
            logger.info(message)
        return None  # 系统控制结果通知不需要响应

# 处理 device_control 类型消息（设备主动请求）
async def handle_device_control(
    message: BaseMessage,
    connection_id: str,
    websocket: WebSocket
    ) -> Optional[dict]:
    if message.event == EventType.GET_RTMP:
        # 获取 RTMP 地址
        return await get_rtmp_address(
            message, connection_id
        )
    elif message.event == EventType.GET_SCREEN:
        # 获取截图地址
        return await get_screen_address(
            message, connection_id
        )
    elif message.event == EventType.POWER_OFF:
        # 关机请求
        return await handle_power_off(
            message, connection_id
        )
    else:
        logger.warning(f"未知的 device_control 事件: {message.event}")
        err_msg = BaseMessage(
            type=MessageType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return err_msg.model_dump()

# 上报设备信息（主动/被动）
async def handle_device_info(
    message: BaseMessage,
    connection_id: str,
    ) -> dict:
    """处理设备信息上报"""
    try:
        # 解析设备信息
        device_info = DeviceInfo(**message.data)
        # 更新管理器中的设备信息
        connectionManager.update_device_info(connection_id, device_info)
        logger.info(f"设备信息更新: {connection_id}")
        # 响应消息
        ret_msg = BaseMessage(
            type=MessageType.S2D_DEVICE_NOTIFY,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=0,
        )
        return ret_msg.model_dump()
        
    except Exception as e:
        logger.error(f"处理设备信息时出错: {e}")
        ret_msg = BaseMessage(
            type=MessageType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return ret_msg.model_dump()

# 处理获取 RTMP 地址请求
async def get_rtmp_address(
    message: BaseMessage,
    connection_id: str
    ) -> dict:
    try:
        rtmp_url = f"rtmp://{settings.video_rtmp_host}:{settings.video_rtmp_port}/live/{connection_id}"
        
        # 获取设备信息中的分辨率等设置
        device_info = connectionManager.get_device_info(connection_id)
        if not device_info:
            raise ValueError(f"设备 {connection_id} 未连接")

        ret_msg = BaseMessage(
            type=MessageType.S2D_DEVICE_NOTIFY,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=0,
            data={
                "rtmp_url": rtmp_url,
                "stream_res": device_info.stream_res if device_info else "720P",
                "stream_bitrate": device_info.stream_bitrate if device_info else 2000000,
                "stream_framerate": device_info.stream_framerate if device_info else 30
            }
        )
        return ret_msg.model_dump()
    except Exception as e:
        logger.error(f"获取RTMP地址时出错: {e}")
        ret_msg = BaseMessage(
            type=MessageType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return ret_msg.model_dump()

# 获取截图上传地址请求（TODO：给一个真实的地址）
async def get_screen_address(
    message: BaseMessage,
    connection_id: str
    ) -> dict:
    """处理获取截图地址请求"""
    try:
        device_status = connectionManager.device_status.get(connection_id)
        if not device_status:
            raise ValueError(f"设备 {connection_id} 未连接")
        
        # 这里应该返回实际的上传地址
        upload_url = f"https://{settings.host}/api/upload/screenshot"
        
        ret_msg = BaseMessage(
            type=MessageType.S2D_DEVICE_NOTIFY,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=0,
            data={
                "screenName": "",
                "deviceId": message.deviceId,
                "url": upload_url,
                "fileBase64": ""
            }
        )
        return ret_msg.model_dump()
    except Exception as e:
        logger.error(f"生成截图地址时出错: {e}")
        ret_msg = BaseMessage(
            type=MessageType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return ret_msg.model_dump()

# 处理关机请求
async def handle_power_off(
    message: BaseMessage,
    connection_id: str
    ) -> dict:
    try:
        logger.info(f"设备请求关机: {connection_id}")
        # 关闭设备连接
        connectionManager.disconnect(connection_id)
        
        ret_msg = BaseMessage(
            type=MessageType.S2D_DEVICE_NOTIFY,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=0,
        )
        return ret_msg.model_dump()
    except Exception as e:
        logger.error(f"处理关机请求时出错: {e}")
        err_msg = BaseMessage(
            type=MessageType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return err_msg.model_dump()
