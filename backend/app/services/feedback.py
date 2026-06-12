"""反馈服务层"""

import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackSummaryResponse

logger = logging.getLogger(__name__)


async def upsert_feedback(
    db: AsyncSession,
    user_id: int,
    message_id: str,
    rating: str,
    comment: str | None = None,
) -> Feedback | None:
    """创建或切换评价。

    如果同一 (user_id, message_id) 已有记录且 rating 相同，则删除（取消评价）。
    如果已有记录但 rating 不同，则更新 rating。
    如果没有记录，则创建新评价。

    Returns:
        Feedback 对象，或 None（取消评价时）。
    """
    stmt = select(Feedback).where(
        Feedback.user_id == user_id,
        Feedback.message_id == message_id,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        if existing.rating == rating:
            # 相同 rating → 取消评价（删除）
            await db.delete(existing)
            await db.commit()
            logger.info("用户 %d 取消了对消息 %s 的 %s 评价", user_id, message_id, rating)
            return None
        else:
            # 不同 rating → 切换
            existing.rating = rating
            if comment is not None:
                existing.comment = comment
            await db.commit()
            await db.refresh(existing)
            logger.info("用户 %d 切换了对消息 %s 的评价为 %s", user_id, message_id, rating)
            return existing
    else:
        fb = Feedback(
            user_id=user_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
        )
        db.add(fb)
        await db.commit()
        await db.refresh(fb)
        logger.info("用户 %d 评价了消息 %s: %s", user_id, message_id, rating)
        return fb


async def get_feedback_summary(
    db: AsyncSession,
    message_id: str,
) -> FeedbackSummaryResponse:
    """获取指定消息的评价统计。"""
    like_stmt = select(func.count(Feedback.id)).where(
        Feedback.message_id == message_id,
        Feedback.rating == "like",
    )
    dislike_stmt = select(func.count(Feedback.id)).where(
        Feedback.message_id == message_id,
        Feedback.rating == "dislike",
    )

    like_count = (await db.execute(like_stmt)).scalar() or 0
    dislike_count = (await db.execute(dislike_stmt)).scalar() or 0

    return FeedbackSummaryResponse(
        message_id=message_id,
        like_count=like_count,
        dislike_count=dislike_count,
    )
