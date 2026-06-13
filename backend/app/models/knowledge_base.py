from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False,
        comment="知识库名称（对应 knowledges/ 下的子目录）"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None,
        comment="知识库描述"
    )
    keywords: Mapped[str | None] = mapped_column(
        String(500), nullable=True, default=None,
        comment="关键词，逗号分隔"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
