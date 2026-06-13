"""向量存储服务

封装 Qdrant 向量数据库操作（混合检索）：
- collection 管理（自动创建，含 dense + sparse 向量配置）
- 向量写入（同时写入稠密向量和文本稀疏向量）
- 混合检索（稠密向量 + BM25 稀疏向量，使用 RRF 融合排序）
- 按文档名删除
"""

import asyncio
import hashlib
import logging
import re
import warnings
from typing import Any

from langchain_core.documents import Document
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

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


def _text_to_sparse_vector(text: str) -> SparseVector:
    """将文本分词并转为 Qdrant SparseVector。

    分词策略（与 Qdrant 搜索端保持一致）：
    - 中文单字切分
    - 英文/数字按单词切分
    - 小写归一化
    - MD5 hash 转整数索引（确保跨进程稳定）
    - 值 = TF（词频），Qdrant 搜索时自动应用 IDF 修正

    Args:
        text: 输入文本

    Returns:
        SparseVector 对象，包含 indices 和 values
    """
    # 提取中文单字 + 英文/数字单词
    tokens = re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9]+", text.lower())

    tf: dict[str, int] = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1

    indices: list[int] = []
    values: list[float] = []
    for token, count in sorted(tf.items(), key=lambda x: -x[1]):
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % (2**31 - 1)
        indices.append(idx)
        values.append(float(count))

    return SparseVector(indices=indices, values=values)


async def ensure_collection() -> None:
    """确保 Qdrant collection 存在，不存在则创建。

    创建时配置：
    - dense: 稠密向量（embedding, 4096 维, 余弦距离）
    - sparse: 稀疏向量（BM25, 关键词检索, IDF 修正）
    """
    client = _get_client()
    collection_name = settings.qdrant_collection_name

    collections = await client.get_collections()
    existing = {c.name for c in collections.collections}

    if collection_name not in existing:
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=settings.embedding_vector_size,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(modifier=Modifier.IDF),
            },
        )
        logger.info(
            "创建 Qdrant collection: %s (dense size=%d, sparse=BM25)",
            collection_name,
            settings.embedding_vector_size,
        )
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

    # 构建所有 points（使用 source+content_hash 作为全局唯一 ID）
    all_points: list[qdrant_models.PointStruct] = []
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        source = chunk.metadata.get("source", "")
        content_hash = int(hashlib.md5((source + chunk.page_content).encode()).hexdigest(), 16) % (2**63 - 1)
        all_points.append(
            qdrant_models.PointStruct(
                id=content_hash,
                vector={
                    "dense": vector,
                    "sparse": _text_to_sparse_vector(chunk.page_content),
                },
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
    query_text: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> list[dict[str, Any]]:
    """在 Qdrant 中做混合检索（稠密向量 + BM25 稀疏向量，RRF 融合排序）。

    双路检索：
    - dense: 语义向量检索（余弦距离）
    - sparse: 关键词检索（BM25, Qdrant 内置 IDF 分词器）

    结果通过 RRF（Reciprocal Rank Fusion）融合排序。

    Args:
        query_vector: 稠密查询向量
        query_text: 原始查询文本（用于 sparse 检索）
        top_k: 返回的最大结果数
        score_threshold: dense 检索的相似度阈值，低于此值的被过滤

    Returns:
        检索结果列表，每个元素包含:
        - source: 来源文件路径
        - section: 章节标题
        - content: 片段原文
        - score: RRF 融合后的排序分数
    """
    client = _get_client()
    collection_name = settings.qdrant_collection_name

    top_k = top_k or settings.qdrant_top_k
    score_threshold = score_threshold if score_threshold is not None else settings.qdrant_score_threshold

    # 双路 prefetch + RRF 融合
    hits = await client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(
                query=query_vector,
                using="dense",
                limit=top_k * 2,
                score_threshold=score_threshold,
            ),
            Prefetch(
                query=_text_to_sparse_vector(query_text),
                using="sparse",
                limit=top_k * 2,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
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
