import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)

class DeviceAuthenticator:
    """设备认证器"""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
    
    def generate_device_token(
        self,
        device_id: str,
        device_sn: str,
        room_id: str,
        expires_hours: int = 24
    ) -> str:
        """生成设备 token"""
        payload = {
            "device_id": device_id,
            "device_sn": device_sn,
            "room_id": room_id,
            "exp": datetime.now(datetime.timezone.utc) + timedelta(hours=expires_hours),
            "iat": datetime.now(datetime.timezone.utc),
            "type": "device"
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    async def verify_token(
        self,
        token: str,
        device_id: str,
        device_sn: str,
        room_id: str
    ) -> bool:
        """验证 token"""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # 验证字段
            if payload.get("device_id") != device_id:
                return False
            
            if payload.get("device_sn") != device_sn:
                return False
            
            if payload.get("room_id") != room_id:
                return False
            
            if payload.get("type") != "device":
                return False
            
            return True
            
        except jwt.ExpiredSignatureError:
            logger.warning(f"Token 已过期: {device_id}")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning(f"无效 Token: {e}")
            return False
        except Exception as e:
            logger.error(f"验证 Token 时出错: {e}")
            return False

async def authenticate_device(
    token: Optional[str],
    device_id: str,
    device_sn: str,
    room_id: str
) -> bool:
    """认证设备"""
    # 如果未配置 SECRET_KEY，跳过认证（仅用于开发）
    if not settings.SECRET_KEY or settings.SECRET_KEY == "your-secret-key-here":
        logger.warning("未配置 SECRET_KEY，跳过设备认证")
        return True
    
    if not token:
        logger.warning(f"设备 {device_id} 未提供 token")
        return False
    
    authenticator = DeviceAuthenticator()
    return await authenticator.verify_token(
        token, device_id, device_sn, room_id
    )
