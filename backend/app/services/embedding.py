"""Embedding 服务

封装 OpenAI 兼容的 Embedding API 调用（当前对接 SiliconFlow），
提供单条和批量文本向量化能力。
"""

import asyncio
import logging

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Embedding API 超时配置
EMBEDDING_TIMEOUT = 30.0
EMBEDDING_MAX_RETRIES = 2
EMBEDDING_RETRY_DELAY = 1.0

# 最大 token 输入长度（Qwen3-Embedding-8B 最大支持 8192 tokens）
MAX_INPUT_LENGTH = 8000

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """延迟初始化 OpenAI 客户端（单例）。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.embedding_api_key,
            base_url=settings.embedding_api_base_url,
            timeout=EMBEDDING_TIMEOUT,
        )
    return _client


def _truncate(text: str, max_chars: int = MAX_INPUT_LENGTH) -> str:
    """截断过长的文本。"""
    return text[:max_chars] if len(text) > max_chars else text


async def embed(text: str) -> list[float]:
    """将单条文本转为向量。

    Args:
        text: 输入文本

    Returns:
        4096 维的浮点数向量

    Raises:
        ValueError: 输入文本为空
        Exception: API 调用失败（含重试后的最终失败）
    """
    if not text or not text.strip():
        raise ValueError("输入文本不能为空")

    text = _truncate(text.strip())
    client = _get_client()

    for attempt in range(EMBEDDING_MAX_RETRIES + 1):
        try:
            response = await client.embeddings.create(
                input=text,
                model=settings.embedding_model,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning("Embedding 调用失败 (第 %d 次): %s", attempt + 1, e)
            if attempt < EMBEDDING_MAX_RETRIES:
                await asyncio.sleep(EMBEDDING_RETRY_DELAY)
            else:
                raise


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """批量将多条文本转为向量。

    Args:
        texts: 输入文本列表

    Returns:
        向量列表，顺序与输入一致
    """
    tasks = [embed(t) for t in texts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    embeddings: list[list[float]] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("批量 embedding 第 %d 条失败: %s", i, result)
            raise result
        embeddings.append(result)

    return embeddings
