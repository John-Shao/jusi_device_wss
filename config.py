import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    
    # 接收X5设备推送视频流的RTMP服务器地址和端口
    video_rtmp_host: str
    video_rtmp_port: int
    
    # 接收VeRTC推送音频流的RTMP服务器地址和端口
    audio_rtmp_host: str
    audio_rtmp_port: int
    
    # 服务器配置
    app_name: str = "DriftSee WebSocket Server"
    app_version: str = "1.5.0"
    host: str = "0.0.0.0"
    port: int = 9000  # WebSocket端点与HTTP API端点共用同一端口
    debug: bool = True
    
    # WebSocket 配置
    websocket_ping_interval: int = 20  # 秒
    websocket_ping_timeout: int = 30   # 秒
    heartbeat_timeout: int = 180       # 3分钟心跳超时
    
    # 安全配置
    secret_key: str = "your_secret key"
    
    # 数据库配置
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@"
    redis_url: str = "redis://jusi:jusi2025@172.18.245.192:6379"  # 测试环境 172.18.245.192
    
    # 文件上传配置
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_image_types: list = ["image/jpeg", "image/png"]
    
    class Config:
        # 指定 .env 文件的编码
        env_file_encoding = 'utf-8'
        # (可选) 如果你的 .env 文件不叫 ".env"，可以在这里指定
        env_file = ".env"
        case_sensitive = False

settings = Settings()
