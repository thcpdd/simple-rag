from datetime import datetime

from pydantic import BaseModel


class KnowledgeDocResponse(BaseModel):
    id: int
    file_path: str
    original_filename: str
    file_size: int
    content_hash: str
    status: str
    chunk_count: int
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeListResponse(BaseModel):
    total: int
    items: list[KnowledgeDocResponse]
