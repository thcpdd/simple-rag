"""Chat API 请求/响应模型"""

from typing import Optional

from pydantic import BaseModel, Field


class ChatInvokeRequest(BaseModel):
    query: str = Field(..., max_length=500, description="用户提问内容，不超过500字")
    thread_id: Optional[str] = Field(None, description="续接已有会话时传入的 thread_id")


class ChatInvokeResponse(BaseModel):
    thread_id: str = Field(..., description="会话线程ID，用于后续流式消费和停止")
    session_id: int = Field(..., description="数据库中的会话记录ID")


class ChatStopRequest(BaseModel):
    thread_id: str = Field(..., description="要停止的会话线程ID")
