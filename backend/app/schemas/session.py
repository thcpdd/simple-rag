"""Session API 请求/响应模型"""

from datetime import datetime

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """会话列表中的单个会话项。"""
    thread_id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """会话列表响应。"""
    total: int
    items: list[SessionResponse]


class SessionMessageResponse(BaseModel):
    """会话中的单条消息。"""
    id: str = Field(default="", description="消息ID")
    role: str = Field(..., description="消息角色: human / ai / tool")
    content: str = Field(default="", description="消息内容")


class SessionDetailResponse(BaseModel):
    """会话详情响应。"""
    thread_id: str
    title: str | None = None
    messages: list[SessionMessageResponse]
