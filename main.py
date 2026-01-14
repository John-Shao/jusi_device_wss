import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from log_mw import RequestLoggingMiddleware
from drift_device_api import device_router
import uvicorn


# 配置日志
log_level=logging.DEBUG if settings.DEBUG else logging.WARNING

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
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # 连接 Redis
    #await manager.connect_redis()
    
    # 启动心跳监控
    #await manager.start_heartbeat_monitor()
    
    logger.info("应用启动完成")
    
    yield  # 应用运行中
    
    # 关闭事件
    logger.info("应用正在关闭...")
    
    # 关闭所有 WebSocket 连接
    #for connection_id in list(manager.active_connections.keys()):
    #    await manager.disconnect(connection_id, reason="服务器关闭")
    
    logger.info("应用已关闭")

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,  # 应用名称
    version=settings.APP_VERSION,  # API的版本
    docs_url="/docs" if settings.DEBUG else None,    # 仅在调试模式下启用Swagger UI文档的访问路径
    redoc_url="/redoc" if settings.DEBUG else None,  # 仅在调试模式下启用ReDoc文档的访问路径
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

# 添加Log中间件
app.add_middleware(RequestLoggingMiddleware)


# 注册路由
app.include_router(device_router, prefix=settings.api_vstr, tags=["Device WSS"])

# 处理根路径请求
@app.get("/")
async def root():
    return {"message": "JUSI Device WebSocket Server"}


# 启动应用
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        reload_dirs=["."],
        ws_ping_interval=settings.WEBSOCKET_PING_INTERVAL,
        ws_ping_timeout=settings.WEBSOCKET_PING_TIMEOUT,
        log_level=log_level
    )
