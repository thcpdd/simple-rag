"""Feedback API 路由

提供以下端点:
1. POST /feedback        — 提交/切换评价
2. GET  /feedback/summary — 获取指定消息的评价统计
"""

import logging

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.feedback import (
    FeedbackCreateRequest,
    FeedbackResponse,
    FeedbackSummaryResponse,
)
from app.services.feedback import get_feedback_summary, upsert_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["反馈"])


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    req: FeedbackCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse | Response:
    """提交或切换对某条消息的评价。"""
    fb = await upsert_feedback(
        db=db,
        user_id=current_user.id,
        message_id=req.message_id,
        rating=req.rating,
        comment=req.comment,
    )
    if fb is None:
        return Response(status_code=204)
    return FeedbackResponse.model_validate(fb)


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def feedback_summary(
    message_id: str = Query(..., min_length=1, max_length=128, description="消息 UUID"),
    db: AsyncSession = Depends(get_db),
) -> FeedbackSummaryResponse:
    """获取指定消息的点赞/踩统计。"""
    return await get_feedback_summary(db, message_id)
