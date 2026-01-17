import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from connection_manager import connectionManager
from drift_websocket_server import drift_websocket_router
from drift_control_server import drift_cloudctrl_router
from cloud_monitor_server import cloud_monitor_router
import uvicorn


# 配置日志
log_level=logging.DEBUG if settings.debug else logging.WARNING

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 定义Lifespan事件
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期事件"""

    # 启动事件
    logger.info(f"启动 {settings.app_name} v{settings.app_version}")

    # 连接redis缓存
    # connectionManager.connect_redis()

    heartbeat_monitor_task = await connectionManager.start_heartbeat_monitor()

    logger.info("应用启动完成")
    
    yield  # 应用运行中
    
    # 关闭事件
    logger.info("应用正在关闭...")

    if heartbeat_monitor_task:
        heartbeat_monitor_task.cancel()
    
    # 关闭所有 WebSocket 连接
    #for device_id in list(manager.active_connections.keys()):
    #    await manager.disconnect(device_id, reason="服务器关闭")

    # 断开redis缓存
    # connectionManager.disconnect_redis()
    
    logger.info("应用已关闭")

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,  # 应用名称
    version=settings.app_version,  # API的版本
    lifespan=lifespan  # 定义一个 lifespan 函数来处理应用启动时和关闭时需要执行的代码，如连接和断开数据库，启动和停止心跳监控任务等
)

# CORS (Cross-Origin Resource Sharing 跨域资源共享)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(drift_websocket_router, prefix=settings.drift_wss_prefix, tags=["Drift WebSocket Server"])
app.include_router(drift_cloudctrl_router, prefix=settings.drift_api_prefix, tags=["Drift Cloud Control"])
app.include_router(cloud_monitor_router, prefix=settings.drift_api_prefix, tags=["Drift Cloud Monitor"])

# 处理根路径请求
@app.get("/")
async def root():
    return {"message": "JUSI Device Real-Time Signaling Server"}


# 启动应用
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["."],
        ws_ping_interval=settings.websocket_ping_interval,
        ws_ping_timeout=settings.websocket_ping_timeout,
        log_level=log_level
    )
