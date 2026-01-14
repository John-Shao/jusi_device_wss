import base64
import logging
from typing import Dict, Any
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)

async def upload_screenshot(upload_data: Dict[str, Any]) -> Dict[str, Any]:
    """上传截图到指定地址"""
    try:
        # 提取必要参数
        screen_name = upload_data.get("screenName", "")
        device_id = upload_data.get("deviceId")
        url = upload_data.get("url")
        room_id = upload_data.get("roomId")
        file_base64 = upload_data.get("fileBase64", "")
        
        if not all([device_id, url, room_id, file_base64]):
            raise ValueError("缺少必要参数")
        
        # 如果 screen_name 为空，生成一个
        if not screen_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screen_name = f"screenshot_{device_id}_{timestamp}.jpg"
        
        # 准备上传数据
        payload = {
            "screenName": screen_name,
            "deviceId": device_id,
            "roomId": room_id,
            "fileBase64": file_base64
        }
        
        # 发送 POST 请求
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"截图上传成功: {screen_name}")
                    return result
                else:
                    error_text = await response.text()
                    raise Exception(f"上传失败: {response.status} - {error_text}")
                    
    except Exception as e:
        logger.error(f"上传截图时出错: {e}")
        raise
    