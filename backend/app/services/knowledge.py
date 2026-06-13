"""知识库服务层

提供知识库文档的 CRUD 操作，包括上传处理（解析→向量化→写入 Qdrant）和删除。
"""

import hashlib
import logging
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_doc import KnowledgeDoc
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate
from app.services.document_parser import parse_document
from app.services.embedding import embed_batch
from app.services.vector_store import delete as delete_vectors
from app.services.vector_store import delete_by_kb as delete_vectors_by_kb
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


# ─── KnowledgeBase CRUD ───


async def create_knowledge_base(
    db: AsyncSession,
    data: KnowledgeBaseCreate,
) -> KnowledgeBase:
    """创建知识库。"""
    kb = KnowledgeBase(
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        keywords=data.keywords.strip() if data.keywords else None,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    logger.info("创建知识库: %s (id=%d)", kb.name, kb.id)
    return kb


async def update_knowledge_base(
    db: AsyncSession,
    kb_id: int,
    data: KnowledgeBaseUpdate,
) -> KnowledgeBase | None:
    """更新知识库元信息。"""
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        return None

    if data.name is not None:
        kb.name = data.name.strip()
    if data.description is not None:
        kb.description = data.description.strip() or None
    if data.keywords is not None:
        kb.keywords = data.keywords.strip() or None

    await db.commit()
    await db.refresh(kb)
    logger.info("更新知识库: %s (id=%d)", kb.name, kb.id)
    return kb


async def delete_knowledge_base(db: AsyncSession, kb_id: int) -> dict:
    """级联删除知识库：删除所有文档的向量、文件、DB 记录，最后删除 KB 记录。

    Returns:
        删除统计: {"deleted_docs": int}
    """
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None:
        return {"deleted_docs": 0}

    kb_name = kb.name

    # 1. 查询该 KB 下所有文档
    result = await db.execute(
        select(KnowledgeDoc).where(KnowledgeDoc.kb_id == kb_id)
    )
    docs = list(result.scalars().all())

    # 2. 删除每个文档的 Qdrant 向量和磁盘文件
    for doc in docs:
        try:
            await delete_vectors(doc.file_path)
        except Exception as e:
            logger.warning("Qdrant 删除失败: %s - %s", doc.file_path, e)

        file_path = KNOWLEDGE_BASE_DIR / doc.file_path
        if file_path.exists():
            file_path.unlink()
            logger.info("已删除磁盘文件: %s", doc.file_path)

    # 3. 级联删除所有 KnowledgeDoc 记录（FK ondelete=CASCADE 也会处理）
    for doc in docs:
        await db.delete(doc)

    # 4. 删除 KnowledgeBase 记录
    await db.delete(kb)
    await db.commit()

    logger.info(
        "知识库已删除: %s (id=%d, 删除文档 %d 篇)",
        kb_name, kb_id, len(docs),
    )
    return {"deleted_docs": len(docs)}


async def get_knowledge_base(db: AsyncSession, kb_id: int) -> KnowledgeBase | None:
    """获取单个知识库。"""
    return await db.get(KnowledgeBase, kb_id)


async def get_knowledge_base_by_name(db: AsyncSession, name: str) -> KnowledgeBase | None:
    """按名称获取知识库。"""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.name == name)
    )
    return result.scalar_one_or_none()


async def list_knowledge_bases(db: AsyncSession) -> list[dict]:
    """获取所有知识库列表及其文档数量。

    Returns:
        格式: [{"id": 1, "name": "auperator", "description": "...", "keywords": "...", "doc_count": 5}, ...]
    """
    # 查询所有知识库
    result = await db.execute(
        select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    )
    kbs = list(result.scalars().all())

    # 统计每个知识库的文档数量
    if not kbs:
        return []

    kb_ids = [kb.id for kb in kbs]
    count_query = (
        select(
            KnowledgeDoc.kb_id,
            func.count(KnowledgeDoc.id).label("doc_count"),
        )
        .where(KnowledgeDoc.kb_id.in_(kb_ids))
        .group_by(KnowledgeDoc.kb_id)
    )
    count_result = await db.execute(count_query)
    doc_counts = {row.kb_id: row.doc_count for row in count_result}

    return [
        {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "keywords": kb.keywords,
            "doc_count": doc_counts.get(kb.id, 0),
            "created_at": kb.created_at,
            "updated_at": kb.updated_at,
        }
        for kb in kbs
    ]


# ─── Document CRUD ───


async def list_docs(
    db: AsyncSession,
    knowledge_base: str | None = None,
    kb_id: int | None = None,
) -> list[KnowledgeDoc]:
    """获取知识库文档列表（按上传时间倒序）。

    Args:
        db: 数据库会话
        knowledge_base: 可选，按知识库名称筛选（旧方式）
        kb_id: 可选，按知识库 ID 筛选（新方式）
    """
    query = select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc())
    if kb_id is not None:
        query = query.where(KnowledgeDoc.kb_id == kb_id)
    elif knowledge_base:
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
    kb_id: int,
    kb_name: str,
) -> KnowledgeDoc:
    """创建初始文档记录（状态：processing），不进行实际处理。

    Args:
        db: 数据库会话
        abs_path: 文档的绝对路径
        kb_id: 知识库 ID
        kb_name: 知识库名称（冗余字段）

    Returns:
        新创建的 KnowledgeDoc 记录
    """
    rel_path = str(abs_path.relative_to(KNOWLEDGE_BASE_DIR))
    md5 = _compute_md5(abs_path)
    file_size = abs_path.stat().st_size

    doc = KnowledgeDoc(
        kb_id=kb_id,
        knowledge_base=kb_name,
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
        kb_name = doc.knowledge_base

        try:
            # 解析
            chunks = parse_document(str(abs_path))

            # 覆盖 source 为相对路径，设置 kb_name
            for chunk in chunks:
                chunk.metadata["source"] = rel_path
                chunk.metadata["kb_name"] = kb_name

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
