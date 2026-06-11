import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.logging.logger import setup_logging
from app.infrastructure.storage.postgres import get_postgres
from app.infrastructure.storage.redis import get_redis
from app.interfaces.endpoints.routes import router
from app.interfaces.errors.exception_handlers import register_exception_handlers
from core.config import get_settings

# 加载配置信息
settings = get_settings()

# 初始化日志系统
setup_logging()
logger = logging.getLogger()

# 定义 FastAPI 路由 tags 标签
openapi_tags = [
    {
        "name": "状态模块",
        "description": "包含 **状态监测** 等API 接口，用于监测系统的运行状态。"
    }
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """创建 FastAPI 应用生命周期上下文管理器"""
    # 重新初始化日志系统（uvicorn 启动时 dictConfig 会影响根日志处理器，需要在此重新配置）
    setup_logging()
    logger.info("MiniManus 正在初始化")

    # 初始化 Redis / Postgres / Cos 客户端
    await get_redis().init()
    await get_postgres().init()

    try:
        yield
    finally:
        # 关闭 Redis / Postgres / Cos 客户端
        await get_redis().shutdown()
        await get_postgres().shutdown()

        logger.info("MiniManus 正在关闭")


# 创建 MiniManus 应用实例
app = FastAPI(
    title="MiniManus 通用智能体",
    description="MiniManus 是一个通用的 AI Agent 系统，可以完全私有部署，使用 A2A + MCP 连接 Agent / Tool，同时支持在沙箱中运行各种内置工具和操作",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
    version="1.0.0",
)

# 配置 CORS 中间件，解决跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册错误处理器
register_exception_handlers(app)

# 集成路由
app.include_router(router, prefix="/api")
