"""知识库服务层

提供知识库文档的 CRUD 操作，包括上传处理（解析→向量化→写入 Qdrant）和删除。
"""

import hashlib
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_doc import KnowledgeDoc
from app.services.document_parser import parse_document
from app.services.embedding import embed_batch
from app.services.vector_store import delete as delete_vectors
from app.services.vector_store import ensure_collection, upsert

logger = logging.getLogger(__name__)

# 文档存储根目录
KNOWLEDGE_BASE_DIR = settings.knowledge_base_path


def _compute_md5(file_path: Path) -> str:
    """计算文件 MD5。"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


async def list_docs(
    db: AsyncSession,
    knowledge_base: str | None = None,
) -> list[KnowledgeDoc]:
    """获取知识库文档列表（按上传时间倒序）。

    Args:
        db: 数据库会话
        knowledge_base: 可选，按知识库名称筛选
    """
    query = select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())
    if knowledge_base:
        query = query.where(KnowledgeDoc.knowledge_base == knowledge_base)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_doc(db: AsyncSession, doc_id: int) -> KnowledgeDoc | None:
    """获取单个知识库文档。"""
    result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
    return result.scalar_one_or_none()


async def create_doc_record(
    db: AsyncSession,
    abs_path: Path,
    knowledge_base: str,
) -> KnowledgeDoc:
    """创建初始文档记录（状态：processing），不进行实际处理。

    Args:
        db: 数据库会话
        abs_path: 文档的绝对路径
        knowledge_base: 知识库名称

    Returns:
        新创建的 KnowledgeDoc 记录
    """
    rel_path = str(abs_path.relative_to(KNOWLEDGE_BASE_DIR))
    md5 = _compute_md5(abs_path)
    file_size = abs_path.stat().st_size

    doc = KnowledgeDoc(
        knowledge_base=knowledge_base,
        file_path=rel_path,
        original_filename=abs_path.name,
        file_size=file_size,
        content_hash=md5,
        status="processing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def process_document_background(doc_id: int, abs_path: Path) -> None:
    """后台处理文档：解析 → 向量化 → 写入 Qdrant → 更新 MySQL。

    使用独立的 DB 会话，适合 FastAPI BackgroundTasks 调用。

    Args:
        doc_id: KnowledgeDoc 记录的 ID
        abs_path: 文档的绝对路径
    """
    from app.core.database import async_session

    async with async_session() as db:
        doc = await db.get(KnowledgeDoc, doc_id)
        if doc is None:
            logger.error("文档记录不存在: id=%d", doc_id)
            return

        rel_path = doc.file_path

        try:
            # 解析
            chunks = parse_document(str(abs_path))

            # 覆盖 source 为相对路径
            for chunk in chunks:
                chunk.metadata["source"] = rel_path

            # 向量化
            texts = [c.page_content for c in chunks]
            embeddings = await embed_batch(texts)

            # 写入 Qdrant
            await ensure_collection()
            await upsert(chunks, embeddings)

            # 更新状态
            doc.status = "ready"
            doc.chunk_count = len(chunks)
            await db.commit()

            logger.info("文档处理完成: %s (%d chunks)", rel_path, len(chunks))

        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            await db.commit()
            logger.error("文档处理失败: %s - %s", rel_path, e)


async def delete_document(db: AsyncSession, doc: KnowledgeDoc) -> None:
    """删除知识库文档：删除 Qdrant 向量 + MySQL 记录。

    Args:
        db: 数据库会话
        doc: 待删除的 KnowledgeDoc 记录
    """
    # 1. 删除 Qdrant 向量
    try:
        await delete_vectors(doc.file_path)
    except Exception as e:
        logger.warning("Qdrant 删除失败（可能已被清理）: %s", e)

    # 2. 可选：删除磁盘文件
    file_path = KNOWLEDGE_BASE_DIR / doc.file_path
    if file_path.exists():
        file_path.unlink()
        logger.info("已删除磁盘文件: %s", doc.file_path)

    # 3. 删除 MySQL 记录
    await db.delete(doc)
    await db.commit()

    logger.info("文档已删除: %s", doc.file_path)


async def list_knowledge_bases(db: AsyncSession) -> list[dict]:
    """获取所有知识库列表及其文档数量（以数据库数据为准）。

    Returns:
        格式: [{"name": "auperator", "doc_count": 5}, ...]
    """
    count_query = (
        select(
            KnowledgeDoc.knowledge_base,
            func.count(KnowledgeDoc.id).label("doc_count"),
        )
        .where(KnowledgeDoc.knowledge_base != "")
        .group_by(KnowledgeDoc.knowledge_base)
        .order_by(KnowledgeDoc.knowledge_base)
    )
    result = await db.execute(count_query)
    return [
        {"name": row.knowledge_base, "doc_count": row.doc_count}
        for row in result
    ]
