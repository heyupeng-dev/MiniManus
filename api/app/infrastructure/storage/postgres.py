import logging
from functools import lru_cache
from typing import Optional, AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine, AsyncSession

from core.config import get_settings

# 创建当前模块的日志记录器
logger = logging.getLogger(__name__)


class Postgres:
    """Postgres 数据库基础类，用于完成数据库连接等配置操作"""

    def __init__(self):
        """构造函数，完成 Postgres 数据库引擎、会话工厂的创建"""
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._settings = get_settings()

    async def init(self) -> None:
        """初始化 Postgres 连接"""
        # 判断是否已经创建好引擎，如果连上了则中断程序
        if self._engine is not None:
            logger.warning(f"Postgres 引擎已初始化，无需重复操作")
            return

        try:
            # 创建异步引擎
            logger.info("正在初始化 Postgres 异步引擎...")
            self._engine = create_async_engine(
                # 数据库连接地址
                self._settings.sqlalchemy_database_uri,
                # 若为开发环境，则打印 SQL 语句，方便调试
                echo=True if self._settings.env == "development" else False,
                # 每次从连接池获取连接前先检测连接是否有效，防止使用已关闭的连接
                pool_pre_ping=True,
            )
            logger.info("Postgres 异步引擎初始化完毕")

            # 创建会话工厂
            logger.info("正在初始化 Postgres 会话工厂...")
            self._session_factory = async_sessionmaker(
                # 禁止自动提交事务，需要手动 commit()
                autocommit=False,
                # 禁止自动把变更同步到数据库
                autoflush=False,
                # 将这个会话工厂绑定到刚刚创建的数据库引擎上
                bind=self._engine,
            )
            logger.info("Postgres 会话工厂初始化完毕")

            # 连接 Postgres 并执行预操作
            async with self._engine.begin() as async_conn:
                # 检查是否安装了 uuid-ossp 扩展，如果没有的话则安装
                await async_conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
                logger.info("成功连接 Postgres 并安装 uuid-ossp 扩展")
        except Exception as e:
            logger.error(f"连接 Postgres 失败: {str(e)}")
            raise

    async def shutdown(self) -> None:
        """关闭 Postgres 连接"""
        if self._engine:
            # 关闭数据库连接池
            await self._engine.dispose()
            # 将异步引擎和会话工厂重新置空
            self._engine = None
            self._session_factory = None
            logger.info("成功关闭 Postgres 连接")

        # 清除 get_postgres() 的缓存，因为使用了 lru_cache()
        get_postgres.cache_clear()

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """只读属性，返回已初始化的会话工厂"""
        if self._session_factory is None:
            raise RuntimeError("Postgres 未初始化，请先调用 init() 函数初始化")
        return self._session_factory


@lru_cache()
def get_postgres() -> Postgres:
    """获取 Postgres 实例"""
    return Postgres()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖项，用于在每个请求中异步获取数据库会话实例，确保会话在正确使用后被关闭"""
    # 获取 Postgres 实例和会话工厂
    db = get_postgres()
    session_factory = db.session_factory

    # 使用会话工厂创建一个新的数据库会话 session，async with 会保证 session 使用结束后自动关闭
    async with session_factory() as session:
        try:
            # 把 session 暂时交给 FastAPI 的接口函数使用，接口函数执行完成后，代码会从 yield 的下一行继续执行
            yield session
            # 如果接口函数没有抛出异常，提交本次数据库事务
            await session.commit()
        except Exception as _:
            # 如果接口函数执行过程中抛出异常，回滚本次数据库事务
            await session.rollback()
            # 把异常继续抛出去，让 FastAPI 或上层异常处理逻辑处理
            raise
