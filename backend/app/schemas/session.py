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
    """会话中的单条消息。

    - human/ai 消息: type + content
    - tool 消息: type + result + args
    """
    id: str
    type: str = Field(..., description="消息类型: human / ai / tool")
    content: str | None = Field(default=None, description="消息内容（human/ai）")
    result: str | None = Field(default=None, description="工具调用结果（tool）")
    args: dict | None = Field(default=None, description="工具调用参数（tool）")
    user_rating: str | None = Field(default=None, description="当前用户对该消息的评价: like/dislike")


class SessionDetailResponse(BaseModel):
    """会话详情响应。"""
    thread_id: str
    title: str | None = None
    messages: list[SessionMessageResponse]
