"""Chat API 路由

提供以下端点:
1. POST /chat/invoke  — 发起 Agent 调用，创建后台任务，返回 thread_id
2. GET  /chat/stream/{thread_id} — SSE 流式消费 Agent 输出
3. POST /chat/stop    — 停止指定后台任务
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.chat import ChatInvokeRequest, ChatInvokeResponse, ChatStopRequest
from app.services import chat_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post("/invoke", response_model=ChatInvokeResponse, status_code=status.HTTP_201_CREATED)
async def invoke_chat(
    req: ChatInvokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatInvokeResponse:
    """发起一个 Agent 调用。

    创建后台任务运行 Agentic RAG，返回 thread_id 供流式消费和停止使用。
    续接已有会话时传入 thread_id，将复用该会话。
    """
    # 校验提问长度
    if len(req.query) > 500:
        raise HTTPException(status_code=400, detail="提问长度不能超过500字")

    if req.thread_id:
        # 续接已有会话：校验会话属于当前用户，不创建新记录
        stmt = select(SessionModel).where(
            SessionModel.thread_id == req.thread_id,
            SessionModel.user_id == current_user.id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="会话不存在")

        thread_id = req.thread_id
        await chat_task_manager.invoke(req.query, thread_id=thread_id)
        logger.info(
            "用户 %d 续接对话: session_id=%d, thread_id=%s",
            current_user.id, session.id, thread_id,
        )
    else:
        # 新建对话
        thread_id = await chat_task_manager.invoke(req.query)

        session = SessionModel(
            user_id=current_user.id,
            thread_id=thread_id,
            title=req.query[:100] if req.query else None,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        logger.info(
            "用户 %d 发起对话: session_id=%d, thread_id=%s",
            current_user.id, session.id, thread_id,
        )

    return ChatInvokeResponse(thread_id=thread_id, session_id=session.id)


@router.get("/stream/{thread_id}")
async def stream_chat(
    thread_id: str,
    current_user: User = Depends(get_current_user),
):
    """SSE 流式接口：根据 thread_id 消费后台任务的 Agent 输出。"""
    async def event_generator():
        try:
            async for event_type, data in chat_task_manager.stream(thread_id):
                if event_type == "token":
                    yield f"data: {json.dumps({'type': 'token', 'content': data}, ensure_ascii=False)}\n\n"
                elif event_type == "tool_call":
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': data['name'], 'args': data['args']}, ensure_ascii=False)}\n\n"
                elif event_type == "tool_result":
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': data['name'], 'result': data['result']}, ensure_ascii=False)}\n\n"
                elif event_type == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': data}, ensure_ascii=False)}\n\n"
                    return
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except asyncio.CancelledError:
            # 客户端断开连接
            logger.info("SSE 客户端断开: thread_id=%s", thread_id)
        except LookupError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("SSE 流异常: thread_id=%s", thread_id)
            yield f"data: {json.dumps({'type': 'error', 'message': '内部错误'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.post("/stop")
async def stop_chat(
    req: ChatStopRequest,
    current_user: User = Depends(get_current_user),
):
    """停止指定 thread_id 的后台 Agent 任务。"""
    try:
        chat_task_manager.stop(req.thread_id)
        logger.info("用户 %d 停止了对话: thread_id=%s", current_user.id, req.thread_id)
        return {"message": "对话已停止", "thread_id": req.thread_id}
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
