import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,      # 回收超过1小时的连接，避免 MySQL wait_timeout
    pool_pre_ping=True,      # 使用连接前验证有效性
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，所有 ORM 模型需继承自此。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话。"""
    async with async_session() as session:
        try:
            yield session
        except asyncio.CancelledError:
            # 请求被取消时（如客户端断开、服务关闭），静默关闭会话
            try:
                await session.close()
            except (RuntimeError, Exception):
                # 事件循环可能已关闭，忽略关闭时的错误
                pass
            raise
        except Exception:
            await session.close()
            raise
