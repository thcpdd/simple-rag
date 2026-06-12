"""向量存储服务

封装 Qdrant 向量数据库操作：
- collection 管理（自动创建）
- 向量写入（带 payload）
- 相似度检索（余弦距离，含阈值过滤）
- 按文档名删除
"""

import asyncio
import logging
import warnings
from typing import Any

from langchain_core.documents import Document
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

warnings.filterwarnings("ignore", message="Api key is used with an insecure connection")
logger = logging.getLogger(__name__)

# 批量写入参数
UPSERT_BATCH_SIZE = 50
UPSERT_TIMEOUT = 120

_client: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    """延迟初始化 Qdrant 客户端（单例）。"""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=f"http://{settings.qdrant_host}:{settings.qdrant_port}",
            api_key=settings.qdrant_api_key or None,
            timeout=UPSERT_TIMEOUT,
        )
    return _client


async def ensure_collection() -> None:
    """确保 Qdrant collection 存在，不存在则创建。

    创建时使用配置的向量维度（4096）和余弦距离。
    """
    client = _get_client()
    collection_name = settings.qdrant_collection_name

    collections = await client.get_collections()
    existing = {c.name for c in collections.collections}

    if collection_name not in existing:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info("创建 Qdrant collection: %s (size=%d)", collection_name, settings.embedding_vector_size)
    else:
        logger.debug("Qdrant collection 已存在: %s", collection_name)


async def upsert(chunks: list[Document], embeddings: list[list[float]]) -> int:
    """将文档分块和对应的向量分批写入 Qdrant。

    Args:
        chunks: 文档分块列表（每个 chunk 的 metadata 需包含 source）
        embeddings: 对应的向量列表，长度必须与 chunks 一致

    Returns:
        写入的向量数量

    Raises:
        ValueError: chunks 和 embeddings 长度不匹配
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"chunks 数量 ({len(chunks)}) 与 embeddings 数量 ({len(embeddings)}) 不匹配"
        )

    client = _get_client()
    collection_name = settings.qdrant_collection_name

    # 构建所有 points（使用整数 ID）
    all_points: list[qdrant_models.PointStruct] = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        all_points.append(
            qdrant_models.PointStruct(
                id=i,
                vector=vector,
                payload={
                    "source": chunk.metadata.get("source", ""),
                    "section": chunk.metadata.get("section", ""),
                    "subsection": chunk.metadata.get("subsection", ""),
                    "content": chunk.page_content,
                    "chunk_index": i,
                },
            )
        )

    # 分批写入，避免单次请求过大导致连接断开
    total = 0
    for batch_start in range(0, len(all_points), UPSERT_BATCH_SIZE):
        batch = all_points[batch_start : batch_start + UPSERT_BATCH_SIZE]
        await client.upsert(
            collection_name=collection_name,
            points=batch,
        )
        total += len(batch)
        logger.info("已写入 %d/%d 个向量", total, len(all_points))
        await asyncio.sleep(0.1)  # 避免请求过密

    logger.info("写入完成: 共 %d 个向量到 Qdrant (collection: %s)", total, collection_name)
    return total


async def search(
    query_vector: list[float],
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """在 Qdrant 中检索最相似的文档片段。

    Args:
        query_vector: 查询向量
        top_k: 返回的最大结果数
        score_threshold: 相似度分数阈值，低于此值的会被过滤

    Returns:
        检索结果列表，每个元素包含:
        - source: 来源文件路径
        - section: 章节标题
        - content: 片段原文
        - score: 相似度分数
    """
    client = _get_client()
    collection_name = settings.qdrant_collection_name

    top_k = top_k or settings.qdrant_top_k
    score_threshold = score_threshold if score_threshold is not None else settings.qdrant_score_threshold

    hits = await client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=top_k,
        score_threshold=score_threshold,
    )

    results: list[dict[str, Any]] = []
    for point in hits.points:
        results.append(
            {
                "source": point.payload.get("source", ""),
                "section": point.payload.get("section", ""),
                "subsection": point.payload.get("subsection", ""),
                "content": point.payload.get("content", ""),
                "score": round(point.score, 4),
            }
        )

    return results


async def delete(source: str) -> int:
    """删除指定来源文档的所有向量。

    Args:
        source: 文档文件路径（与 upsert 时 metadata 中的 source 一致）

    Returns:
        删除的向量数量
    """
    client = _get_client()
    collection_name = settings.qdrant_collection_name

    result = await client.delete(
        collection_name=collection_name,
        points_selector=qdrant_models.Filter(
            must=[
                qdrant_models.FieldCondition(
                    key="source",
                    match=qdrant_models.MatchValue(value=source),
                )
            ]
        ),
    )

    logger.info("从 Qdrant 删除 source=%s 的向量", source)
    return result.status  # type: ignore[return-value]
