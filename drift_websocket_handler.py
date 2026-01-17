import logging
from typing import Optional
from models import (
    DriftMessage, DriftMessage, DriftEvent, DriftMsgType, DeviceInfo
)
from connection_manager import connectionManager
from config import settings


logger = logging.getLogger(__name__)

# 处理设备发送的消息
async def handle_device_message(
    message_data: dict,
    device_id: str,
    ) -> Optional[dict]:
    """处理设备消息"""
    try:
        # 验证消息格式
        message = DriftMessage(**message_data)
        
        # 根据消息类型处理
        if message.type == DriftMsgType.D2S_NOTIFY:
            return await handle_notify_message(message, device_id)
        elif message.type == DriftMsgType.D2S_DEVICE_CONTROL:
            return await handle_device_control(message, device_id)
        else:
            logger.warning(f"不支持的消息类型: {message.type}")
            err_msg = DriftMessage(
                type=DriftMsgType.S2D_MESSAGE,
                event=message.event,
                deviceId=message.deviceId,
                playId=message.playId,
                code=-1,
            )
            return err_msg.model_dump()
            
    except Exception as e:
        logger.error(f"处理消息时出错: {e}")
        err_msg = DriftMessage(
                type=DriftMsgType.S2D_MESSAGE,
                event=message.event,
                deviceId=message.deviceId,
                playId=message.playId,
                code=-1,
            )
        return err_msg.model_dump()


# 处理 notify 类型消息
async def handle_notify_message(
    message: DriftMessage,
    device_id: str,
    ) -> Optional[dict]:
    # 更新心跳时间
    await connectionManager.update_heartbeat(device_id)
    
    if message.event == DriftEvent.JOIN:
        logger.debug(f"收到心跳: {device_id}")
        return None  # 心跳不需要处理，也不需要响应
        
    elif message.event == DriftEvent.DEVICE_INFO:
        # 设备信息上报
        return await handle_device_info(
            message, device_id
        )
    else:
        # 系统控制（control）结果通知
        if message.code:
            message = f"设备 {device_id} 处理 {message.event} 指令失败，错误码: {message.code}"
            logger.warning(message)
        else:
            message = f"设备 {device_id} 处理 {message.event} 指令成功"
            logger.info(message)
        return None  # 系统控制结果通知不需要响应

# 处理 device_control 类型消息（设备主动请求）
async def handle_device_control(
    message: DriftMessage,
    device_id: str,
    ) -> Optional[dict]:
    if message.event == DriftEvent.GET_RTMP:
        # 获取 RTMP 地址
        return await get_rtmp_address(
            message, device_id
        )
    elif message.event == DriftEvent.GET_SCREEN:
        # 获取截图地址
        return await get_screen_address(
            message, device_id
        )
    elif message.event == DriftEvent.POWER_OFF:
        # 关机请求
        return await handle_power_off(
            message, device_id
        )
    else:
        logger.warning(f"未知的 device_control 事件: {message.event}")
        err_msg = DriftMessage(
            type=DriftMsgType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return err_msg.model_dump()

# 上报设备信息（主动/被动）
async def handle_device_info(
    message: DriftMessage,
    device_id: str,
    ) -> dict:
    """处理设备信息上报"""
    try:
        # 解析设备信息
        device_info = DeviceInfo(**message.data)
        # 更新管理器中的设备信息
        connectionManager.update_device_info(device_id, device_info)
        logger.info(f"设备信息已更新: {device_id}")
    except Exception as e:
        logger.error(f"处理设备信息时出错: {e}")
    return None  # 通知类消息不需要响应

# 处理获取 RTMP 地址请求
async def get_rtmp_address(
    message: DriftMessage,
    device_id: str
    ) -> dict:
    try:
        rtmp_url = f"rtmp://{settings.video_rtmp_host}:{settings.video_rtmp_port}/live/{device_id}"
        
        # 获取设备信息中的分辨率等设置
        device_status = connectionManager.get_device_status(device_id)
        if not device_status:
            raise ValueError(f"设备 {device_id} 未连接")
        device_info = device_status.device_info
        ret_msg = DriftMessage(
            type=DriftMsgType.S2D_DEVICE_NOTIFY,
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
        ret_msg = DriftMessage(
            type=DriftMsgType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return ret_msg.model_dump()

# 获取截图上传地址请求（TODO：给一个真实的地址）
async def get_screen_address(
    message: DriftMessage,
    device_id: str
    ) -> dict:
    """处理获取截图地址请求"""
    try:
        device_status = connectionManager._device_status.get(device_id)
        if not device_status:
            raise ValueError(f"设备 {device_id} 未连接")
        
        # 这里应该返回实际的上传地址
        upload_url = f"https://{settings.host}/api/upload/screenshot"
        
        ret_msg = DriftMessage(
            type=DriftMsgType.S2D_DEVICE_NOTIFY,
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
        ret_msg = DriftMessage(
            type=DriftMsgType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return ret_msg.model_dump()

# 处理关机请求
async def handle_power_off(
    message: DriftMessage,
    device_id: str
    ) -> dict:
    try:
        logger.info(f"设备请求关机: {device_id}")
        # 关闭设备连接
        connectionManager.disconnect(device_id)
        
        ret_msg = DriftMessage(
            type=DriftMsgType.S2D_DEVICE_NOTIFY,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
        )
        return ret_msg.model_dump()
    except Exception as e:
        logger.error(f"处理关机请求时出错: {e}")
        err_msg = DriftMessage(
            type=DriftMsgType.S2D_MESSAGE,
            event=message.event,
            deviceId=message.deviceId,
            playId=message.playId,
            code=-1,
        )
        return err_msg.model_dump()
