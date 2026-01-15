
import json
import logging
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect, APIRouter

from connection_manager import connectionManager
from device_handler import DeviceMessageHandler


logger = logging.getLogger(__name__)

drift_router = APIRouter()

# 设备 WebSocket 连接端点（websocket_server_url）
# /api/ws/v1/manyRoom/f2374f8400a763e03e35745d71b01275/74TNABDGNAA0YW01/device/00a4b5697e3d16796b818d656ccea433/zh-CN
@drift_router.websocket("/manyRoom/{room_id}/{device_sn}/device/{device_id}/{language}")
async def drift_websocket(
    room_id: str,
    device_sn: str,
    websocket: WebSocket,
    device_id: str,
    language: str = "zh-CN"
    ):
    """Drift 设备 WebSocket 连接端点"""
    '''
    # 设备认证
    is_authenticated = await authenticate_device(token, device_id)
    if not is_authenticated:
        await websocket.close(code=1008, reason="认证失败")
        return
    '''

    # 建立连接
    connection_id = await connectionManager.connect(websocket, room_id, device_sn, device_id, language)
    
    try:
        while True:
            # 接收消息
            message_data = await websocket.receive_json()
            logger.debug(f"收到消息: {json.dumps(message_data, indent=2)}")
            
            # 处理消息
            response = await DeviceMessageHandler.handle_message(
                message_data, connection_id, websocket
            )
            
            # 发送响应
            if response:
                await websocket.send_json(response)
                logger.debug(f"发送响应: {json.dumps(response, indent=2)}")
            
    except WebSocketDisconnect as e:
        logger.info(f"设备断开连接: {connection_id}, 代码: {e.code}")
        await connectionManager.disconnect(connection_id)
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析错误: {e}")
        await connectionManager.disconnect(
            connection_id,
            code=1007,
            reason="消息格式错误"
        )
    except Exception as e:
        logger.error(f"处理 WebSocket 时出错: {e}")
        await connectionManager.disconnect(
            connection_id,
            code=1011,
            reason="服务器内部错误"
        )
