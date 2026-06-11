from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MiniManus 后端中控配置信息，从 .env 或者环境变量中加载数据"""

    # 项目基础配置
    env: str = "development"
    log_level: str = "INFO"
    app_config_filepath: str = "config.yaml"

    # 数据库配置
    sqlalchemy_database_uri: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/manus"

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    # Cos 腾讯云对象存储配置
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = ""
    cos_scheme: str = "https"
    cos_bucket: str = ""
    cos_domain: str = ""

    # Sandbox 配置
    sandbox_address: Optional[str] = None
    sandbox_image: Optional[str] = None
    sandbox_name_prefix: Optional[str] = None
    sandbox_ttl_minutes: Optional[int] = 60
    sandbox_network: Optional[str] = None
    sandbox_chrome_args: Optional[str] = ""
    sandbox_https_proxy: Optional[str] = None
    sandbox_http_proxy: Optional[str] = None
    sandbox_no_proxy: Optional[str] = None

    # 加载外部配置
    model_config = SettingsConfigDict(
        # 开发环境配置文件；相对路径会从当前运行目录开始查找
        env_file=".env.dev",
        # 按 UTF-8 读取配置文件，避免中文注释或特殊字符出现编码问题
        env_file_encoding="utf-8",
        # 配置文件中如果出现 Settings 没有声明的配置项，直接忽略，不抛异常
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """获取当前 MiniManus 项目的配置信息，并对内容进行缓存，避免重复读取"""
    settings = Settings()
    return settings


if __name__ == "__main__":
    settings = get_settings()
    print(settings)
