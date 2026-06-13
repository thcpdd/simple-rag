from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kb_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True, index=True,
        comment="关联的知识库 ID"
    )
    knowledge_base: Mapped[str] = mapped_column(
        String(100), nullable=False, default="",
        comment="知识库名称（按 knowledges/ 下的子目录划分），冗余字段，优先使用 kb_id"
    )
    file_path: Mapped[str] = mapped_column(
        String(500), unique=True, nullable=False,
        comment="knowledges/ 下的相对路径"
    )
    original_filename: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="原始文件名，前端展示用"
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        comment="文件 MD5，用于重复检测"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="processing",
        comment="processing / ready / failed"
    )
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
