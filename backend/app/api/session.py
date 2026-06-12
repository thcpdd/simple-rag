"""Session API 路由

提供以下端点:
1. GET /session/list       — 获取当前用户的所有会话列表
2. GET /session/{thread_id} — 获取指定会话的详细聊天记录（通过 LangGraph Checkpointer）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.session import (
    SessionDetailResponse,
    SessionListResponse,
    SessionMessageResponse,
    SessionResponse,
)
from app.services import chat_task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["会话"])


@router.get("/list", response_model=SessionListResponse)
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有会话列表，按更新时间倒序排列。"""
    result = await db.execute(
        select(SessionModel)
        .where(SessionModel.user_id == current_user.id)
        .order_by(SessionModel.updated_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListResponse(
        total=len(sessions),
        items=[SessionResponse.model_validate(s) for s in sessions],
    )


@router.get("/{thread_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取指定会话的详细聊天记录。

    通过 LangGraph Checkpointer 恢复该 thread_id 对应的完整对话上下文。
    """
    # 1. 验证会话存在且属于当前用户
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.thread_id == thread_id,
            SessionModel.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )

    # 2. 从 Checkpointer 获取对话状态
    try:
        state = await chat_task_manager.get_state(thread_id)
    except Exception as e:
        logger.exception("获取对话状态失败: thread_id=%s", thread_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取对话记录失败: {e}",
        )

    # 3. 解析消息列表
    messages: list[SessionMessageResponse] = []
    if state and state.values and "messages" in state.values:
        raw_messages = state.values["messages"]

        # 第一遍：收集所有工具调用 ID → 参数 的映射
        tool_call_args: dict[str, dict] = {}
        for msg in raw_messages:
            tcs = getattr(msg, "tool_calls", None)
            if tcs:
                for tc in tcs:
                    tool_call_args[tc["id"]] = tc.get("args", {})

        # 第二遍：生成消息列表
        for msg in raw_messages:
            msg_type = getattr(msg, "type", "unknown")

            # 跳过 AI 工具调用消息（content 为空，仅有 tool_calls）
            if msg_type == "ai" and getattr(msg, "tool_calls", None):
                continue

            if msg_type == "tool":
                tc_id = getattr(msg, "tool_call_id", "")
                messages.append(
                    SessionMessageResponse(
                        type="tool",
                        result=getattr(msg, "content", ""),
                        args=tool_call_args.get(tc_id, {}),
                    )
                )
            else:
                messages.append(
                    SessionMessageResponse(
                        type=msg_type,
                        content=getattr(msg, "content", ""),
                    )
                )

    return SessionDetailResponse(
        thread_id=thread_id,
        title=session.title,
        messages=messages,
    )


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除指定会话。

    1. 验证会话存在且属于当前用户
    2. 停止正在运行的任务（若有）
    3. 删除 Checkpointer 中的 checkpoint 数据
    4. 删除 MySQL sessions 记录
    """
    # 1. 验证会话存在且属于当前用户
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.thread_id == thread_id,
            SessionModel.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="会话不存在",
        )

    # 2. 停止正在运行的任务（若有）
    try:
        chat_task_manager.stop(thread_id)
    except LookupError:
        pass  # 没有运行中的任务，忽略
    except Exception as e:
        logger.warning("停止任务失败: thread_id=%s, error=%s", thread_id, e)

    # 3. 删除 Checkpointer 中的 checkpoint 数据
    try:
        await chat_task_manager.delete_thread_checkpoints(thread_id)
    except Exception as e:
        logger.warning("删除 Checkpointer 数据失败: thread_id=%s, error=%s", thread_id, e)

    # 4. 删除 MySQL sessions 记录
    await db.delete(session)
    await db.commit()

    logger.info("会话已删除: thread_id=%s, user_id=%s", thread_id, current_user.id)
