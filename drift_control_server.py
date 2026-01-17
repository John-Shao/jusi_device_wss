import json
import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, APIRouter
from fastapi.responses import JSONResponse
from config import settings
from models import DriftMessage, DriftMessage
from connection_manager import connectionManager


logger = logging.getLogger(__name__)

drift_cloudctrl_router = APIRouter()

# 设备云控API
@drift_cloudctrl_router.post("/cloud-control")
async def drift_cloud_control_handler(request: dict):
    try:
        msg = DriftMessage(**request)
        await connectionManager.send_message(msg.deviceId, request)
        return msg.model_dump()
        
    except Exception as e:
        logger.error(f"发送控制命令失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
