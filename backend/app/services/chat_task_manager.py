"""Chat 任务管理器

管理 Agent 后台任务的启动、流式消费与停止。
使用 LangGraph 的 AIOMySQLSaver 进行会话持久化。

架构说明:
- invoke() 创建一个新 thread_id，启动后台 asyncio.Task 运行 Agent
- Agent 通过 astream_events 产出 token，通过 asyncio.Queue 传递给 SSE 端点
- stream() 从 Queue 中消费事件（token / sources / done / error）
- stop() 取消对应的 asyncio.Task
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from uuid import uuid4

import aiomysql
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.mysql.aio import AIOMySQLSaver

from app.agents.builder import build_agent
from app.core.config import settings

logger = logging.getLogger(__name__)

# ========== 全局状态 ==========

_tasks: Dict[str, asyncio.Task] = {}       # thread_id -> asyncio.Task
_queues: Dict[str, asyncio.Queue] = {}     # thread_id -> asyncio.Queue
_errors: Dict[str, str] = {}               # thread_id -> error message

_checkpointer: Optional[AIOMySQLSaver] = None
_conn: Optional[aiomysql.Connection] = None
_agent = None


# ========== 延迟初始化（单例） ==========

async def _get_checkpointer() -> AIOMySQLSaver:
    """获取或初始化 AIOMySQLSaver 检查点器。"""
    global _checkpointer, _conn
    if _checkpointer is None:
        db_url = settings.database_url
        logger.info("初始化 Chat Checkpointer: %s", db_url)
        conn_kwargs = AIOMySQLSaver.parse_conn_string(db_url)
        _conn = await aiomysql.connect(**conn_kwargs, autocommit=True)
        _checkpointer = AIOMySQLSaver(conn=_conn)
        await _checkpointer.setup()  # 创建 checkpoint 相关表
        logger.info("Chat Checkpointer 初始化完成")
    return _checkpointer


async def _get_agent():
    """获取或初始化带 Checkpointer 的 Agent。"""
    global _agent
    if _agent is None:
        checkpointer = await _get_checkpointer()
        _agent = build_agent(checkpointer=checkpointer)
        logger.info("Chat Agent 初始化完成")
    return _agent


# ========== 公开 API ==========


async def invoke(query: str) -> str:
    """发起一个 Agent 后台调用。

    Args:
        query: 用户提问文本

    Returns:
        thread_id: 用于后续流式消费和停止的唯一线程ID
    """
    thread_id = str(uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _queues[thread_id] = queue
    _errors.pop(thread_id, None)

    agent = await _get_agent()
    task = asyncio.create_task(_run_agent(agent, thread_id, query, queue))
    _tasks[thread_id] = task
    task.add_done_callback(lambda _: _cleanup_later(thread_id))

    logger.info("Chat 任务已创建: thread_id=%s, query=%.50s", thread_id, query)
    return thread_id


async def stream(thread_id: str) -> AsyncGenerator[Tuple[str, Any], None]:
    """消费指定 thread_id 的后台任务输出流。

    Yields:
        (event_type, data) 元组:
        - ("token", token_text)  LLM 生成的文本片段
        - ("sources", source_list)  知识来源列表
        - ("error", error_message)  任务出错
        - （"done", None 不 yield，通过生成器结束指示）
    """
    queue = _queues.get(thread_id)
    if queue is None:
        raise LookupError(f"thread_id '{thread_id}' 不存在或任务已结束")

    while True:
        event_type, data = await queue.get()
        if event_type == "done":
            break
        yield event_type, data


def stop(thread_id: str) -> None:
    """停止指定 thread_id 的后台任务。"""
    task = _tasks.get(thread_id)
    if task is None:
        raise LookupError(f"thread_id '{thread_id}' 不存在或任务已结束")
    task.cancel()
    _cleanup(thread_id)
    logger.info("Chat 任务已停止: thread_id=%s", thread_id)


async def shutdown() -> None:
    """关闭 Checkpointer 连接池（应用关闭时调用）。"""
    global _checkpointer, _agent, _conn
    # 取消所有运行中的任务
    for tid in list(_tasks.keys()):
        stop(tid)
    # 关闭 MySQL 连接
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            logger.exception("关闭 MySQL 连接时出错")
        _conn = None
    _checkpointer = None
    _agent = None
    logger.info("Chat 任务管理器已关闭")


# ========== 内部实现 ==========


async def _run_agent(agent, thread_id: str, query: str, queue: asyncio.Queue) -> None:
    """在后台运行 Agent，将事件推入 Queue。"""
    try:
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": "",
            }
        }
        input_msg = {"messages": [HumanMessage(content=query)]}

        sources: list[str] = []

        async for event in agent.astream_events(input_msg, config, version="v2"):
            kind = event.get("event")

            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content"):
                    content = chunk.content
                    if content:
                        await queue.put(("token", content))

            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                # output 可能是 ToolMessage 对象，提取其文本内容
                if hasattr(output, "content"):
                    text = output.content
                else:
                    text = str(output)
                if text:
                    sources.append(text)

        # 流结束后发送知识来源
        if sources:
            await queue.put(("sources", sources))

        await queue.put(("done", None))
        logger.info("Chat 任务完成: thread_id=%s", thread_id)

    except asyncio.CancelledError:
        logger.info("Chat 任务被取消: thread_id=%s", thread_id)
        await queue.put(("done", None))
    except Exception as e:
        logger.exception("Chat 任务异常: thread_id=%s", thread_id)
        _errors[thread_id] = str(e)
        await queue.put(("error", str(e)))


def _cleanup(thread_id: str) -> None:
    """立即清理指定 thread_id 的状态。"""
    _tasks.pop(thread_id, None)
    _queues.pop(thread_id, None)
    _errors.pop(thread_id, None)


def _cleanup_later(thread_id: str) -> None:
    """任务完成回调：延迟清理状态，给 stream() 留出消费时间。"""
    _tasks.pop(thread_id, None)
    # Queue 保留在 _queues 中，直到 stream() 消费完毕
    # 通过 asyncio 的事件循环延迟清理
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.call_later(60, lambda: _queues.pop(thread_id, None) or _errors.pop(thread_id, None))
