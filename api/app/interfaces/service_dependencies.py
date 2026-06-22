import logging
from functools import lru_cache

from app.application.services.app_config_services import AppConfigService
from app.infrastructure.repositories.file_app_config_repository import FileAppConfigRepository
from core.config import get_settings

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)

settings = get_settings()

@lru_cache
def get_app_config_service() -> AppConfigService:
    """获取应用配置服务"""
    # 获取数据仓库并打印日志
    logger.info("加载获取 AppConfigService")
    file_app_config_repository = FileAppConfigRepository(settings.app_config_filepath)

    # 实例化 AppConfigService
    return AppConfigService(app_config_repository=file_app_config_repository)