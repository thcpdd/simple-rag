from datetime import datetime, timezone, timedelta

from pydantic import BaseModel
from pydantic.functional_serializers import field_serializer

# 上海时区 (UTC+8)
SHANGHAI_TZ = timezone(timedelta(hours=8))


class KnowledgeDocResponse(BaseModel):
    id: int
    kb_id: int | None = None
    knowledge_base: str
    file_path: str
    original_filename: str
    file_size: int
    content_hash: str
    status: str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def convert_to_shanghai(self, dt: datetime) -> datetime:
        """将 UTC 时间转为上海时区（UTC+8）。"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(SHANGHAI_TZ)


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeDocResponse]


class KnowledgeBaseItem(BaseModel):
    name: str
    doc_count: int


class KnowledgeBaseListResponse(BaseModel):
    total: int
    items: list[KnowledgeBaseItem]


# ─── KnowledgeBase CRUD Schemas ───

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    keywords: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    keywords: str | None = None


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    keywords: str | None = None
    doc_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "updated_at")
    def convert_to_shanghai(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(SHANGHAI_TZ)


class KnowledgeBaseDeleteResponse(BaseModel):
    message: str
    deleted_docs: int
