from app.domain.models.app_config import AppConfig, LLMConfig
from app.domain.repositories.app_config_repository import AppConfigRepository


class AppConfigService:
    """应用配置服务"""

    def __init__(self, app_config_repository: AppConfigRepository) -> None:
        """构造函数，完成应用配置服务的初始化"""
        self.app_config_repository = app_config_repository

    async def _load_app_config(self) -> AppConfig | None:
        """加载获取所有的应用配置"""
        return self.app_config_repository.load()

    async def get_llm_config(self) -> LLMConfig:
        """获取 LLM 提供商配置"""
        app_config = await self._load_app_config()
        return app_config.llm_config

    async def update_llm_config(self, llm_config: LLMConfig) -> LLMConfig:
        """根据传递的 llm_config 更新语言模型提供商配置"""
        # 获取应用配置
        app_config = await self._load_app_config()

        # 判断api_key是否为空
        if not llm_config.api_key.strip():
            llm_config.api_key = app_config.llm_config.api_key

        # 调用函数更新 app_config
        app_config.llm_config = llm_config
        self.app_config_repository.save(app_config)

        return app_config.llm_config