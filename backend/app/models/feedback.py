from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.mysql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(
        String(128), nullable=False,
        comment="被评价消息在 LangGraph Checkpointer 中的 UUID"
    )
    rating: Mapped[str] = mapped_column(
        ENUM("like", "dislike"), nullable=False,
        comment="like=点赞, dislike=点踩"
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="用户可选评价备注")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("user_id", "message_id", name="uq_user_message"),
    )
