"""Feedback API 请求/响应模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    message_id: str = Field(..., max_length=128, description="被评价消息的 UUID")
    rating: str = Field(..., pattern="^(like|dislike)$", description="like 或 dislike")
    comment: Optional[str] = Field(None, max_length=500, description="可选评价备注")


class FeedbackResponse(BaseModel):
    id: int
    message_id: str
    rating: str
    comment: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackSummaryResponse(BaseModel):
    message_id: str
    like_count: int = Field(default=0)
    dislike_count: int = Field(default=0)
