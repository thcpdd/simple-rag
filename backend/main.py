from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.auth import router as auth_router
from app.api.knowledge import router as knowledge_router
from app.api.chat import router as chat_router
from app.api.session import router as session_router
from app.api.feedback import router as feedback_router
from app.services import chat_task_manager
from app.utils.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时创建表结构，关闭时释放连接池。"""
    # 初始化统一日志
    setup_logging(level="DEBUG" if settings.debug else "INFO")

    # 导入所有模型，确保 Base.metadata 中包含完整的表结构
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield
    await chat_task_manager.shutdown()
    await engine.dispose()


app = FastAPI(
    title="AI 智能客服系统",
    version="0.1.0",
    lifespan=lifespan,
)

@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(feedback_router)

if __name__ == "__main__":
    import uvicorn

    from app.utils.logging import get_uvicorn_log_config

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_config=get_uvicorn_log_config(
            level="DEBUG" if settings.debug else "INFO",
        ),
    )
