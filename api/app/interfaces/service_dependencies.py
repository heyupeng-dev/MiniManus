import logging
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.app_config_services import AppConfigService
from app.application.services.status_service import StatusService
from app.infrastructure.external.health_checker.postgres_health_checker import PostgresHealthChecker
from app.infrastructure.external.health_checker.redis_health_checker import RedisHealthChecker
from app.infrastructure.repositories.file_app_config_repository import FileAppConfigRepository
from app.infrastructure.storage.postgres import get_db_session
from app.infrastructure.storage.redis import RedisClient, get_redis
from core.config import get_settings

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)

# 加载应用配置
settings = get_settings()


@lru_cache
def get_app_config_service() -> AppConfigService:
    """获取应用配置服务"""

    # 记录 AppConfigService 开始加载
    logger.info("加载获取 AppConfigService")

    # 创建基于文件的应用配置仓库，其文件路径从 settings 中获取
    file_app_config_repository = FileAppConfigRepository(settings.app_config_filepath)

    # 使用配置仓库创建应用配置服务
    return AppConfigService(app_config_repository=file_app_config_repository)


@lru_cache()
def get_status_service(
        db_session: AsyncSession = Depends(get_db_session),
        redis_client: RedisClient = Depends(get_redis),
) -> StatusService:
    """获取系统状态服务，用于检查外部依赖是否正常"""

    # 使用当前请求注入的数据库会话创建 Postgres 健康检查器
    postgres_checker = PostgresHealthChecker(db_session)
    # 使用当前请求注入的 Redis 客户端创建 Redis 健康检查器
    redis_checker = RedisHealthChecker(redis_client)

    # 记录 StatusService 开始加载
    logger.info("加载获取 StatusService")

    # 将所有健康检查器组合到状态服务中，后续可统一执行健康检查
    return StatusService(checkers=[postgres_checker, redis_checker])
