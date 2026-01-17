# Drift 设备 WebSocket 连接端点
import json
import logging
from fastapi import (
    WebSocket,
    WebSocketDisconnect,
    APIRouter, 
    BackgroundTasks,
    WebSocketException,
    )
from connection_manager import connectionManager
from drift_websocket_handler import handle_device_message


logger = logging.getLogger(__name__)

drift_websocket_router = APIRouter()

# 设备 WebSocket 连接端点（websocket_server_url）
# /api/ws/v1/manyRoom/f2374f8400a763e03e35745d71b01275/74TNABDGNAA0YW01/device/00a4b5697e3d16796b818d656ccea433/zh-CN
@drift_websocket_router.websocket("/manyRoom/{room_id}/{device_sn}/device/{device_id}/{language}")
async def drift_websocket(
    room_id: str,
    device_sn: str,
    websocket: WebSocket,
    device_id: str,
    background_tasks: BackgroundTasks,
    language: str = "zh-CN",
    ):
    """Drift 设备 WebSocket 连接端点"""

    # TODO：设备认证

    # 建立连接
    await connectionManager.connect(websocket, room_id, device_sn, device_id, language)
    # 接收并处理连接中的消息
    await handle_connection_message(device_id)

# 处理单个设备连接发送的消息
async def handle_connection_message(
    device_id: str,
    ):
    """处理设备连接"""
    try:
        while True:
            if not connectionManager.connected(device_id):
                break
            # 接收消息
            message_data = await connectionManager.receive_message(device_id)
            # 处理消息
            response = await handle_device_message(message_data, device_id)
            # 发送响应
            if response:
                await connectionManager.send_message(device_id, response)
    except Exception as e:
        logger.error(f"处理 WebSocket 时出错: {e}")
        await connectionManager.disconnect(
            device_id,
            code=1011,
            reason=f"{e}"
        )
