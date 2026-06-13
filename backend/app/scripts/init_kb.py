"""知识库初始化脚本

将 knowledges/ 目录下的所有文档解析、向量化、写入 Qdrant 和 MySQL。

幂等功能：
- 计算文件 MD5，已在 MySQL 中存在的文件自动跳过
- 可安全重复运行

使用方式:
    python -m app.scripts.init_kb
"""

import asyncio
import hashlib
import logging
import time
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import Base, async_session, engine
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_doc import KnowledgeDoc
from app.services.document_parser import parse_document
from app.services.embedding import embed_batch
from app.services.vector_store import ensure_collection, upsert
from app.utils.logging import setup_logging

setup_logging(level="INFO")
logger = logging.getLogger(__name__)

# 知识库根目录
KNOWLEDGE_BASE_DIR = settings.knowledge_base_path


def _compute_md5(file_path: Path) -> str:
    """计算文件 MD5。"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _discover_documents() -> list[Path]:
    """扫描知识库目录，发现所有支持的文档文件。

    Returns:
        按文件名排序的文档路径列表
    """
    supported = (".md", ".txt")
    files: list[Path] = []
    for ext in supported:
        files.extend(KNOWLEDGE_BASE_DIR.rglob(f"*{ext}"))
    # 跳过 uploads 目录
    files = [f for f in files if "uploads" not in f.parts]
    return sorted(files)


def _extract_knowledge_base(rel_path: str) -> str:
    """从相对路径中提取知识库名称（第一个子目录）。"""
    parts = rel_path.replace("\\", "/").split("/")
    return parts[0] if parts else "default"


async def _ensure_knowledge_base(db, kb_name: str) -> KnowledgeBase:
    """确保知识库记录存在，不存在则创建。

    Returns:
        KnowledgeBase 对象
    """
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.name == kb_name)
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        kb = KnowledgeBase(name=kb_name)
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        logger.info("自动创建知识库: %s (id=%d)", kb.name, kb.id)
    return kb


async def main() -> None:
    """主流程：扫描 → 去重 → 解析 → 向量化 → 写入 Qdrant + MySQL。"""
    start_time = time.time()

    # 1. 确保表存在
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. 确保 Qdrant collection 存在
    logger.info("连接 Qdrant...")
    await ensure_collection()

    try:
        # 3. 扫描文档
        files = _discover_documents()
        if not files:
            logger.warning("在 %s 下未找到 .md / .txt 文件", KNOWLEDGE_BASE_DIR)
            return

        logger.info("扫描到 %d 个文档文件:", len(files))
        for f in files:
            logger.info("  - %s", f.relative_to(KNOWLEDGE_BASE_DIR))

        # 4. 查询 MySQL 已有记录的 content_hash，用于去重
        async with async_session() as db:
            result = await db.execute(select(KnowledgeDoc.content_hash))
            existing_hashes = {row[0] for row in result.fetchall()}
        logger.info("MySQL 中已有 %d 条知识库记录", len(existing_hashes))

        # 5. 逐文件处理
        total_new_files = 0
        total_chunks: list = []
        file_records: list[KnowledgeDoc] = []

        for file_path in files:
            rel_path = str(file_path.relative_to(KNOWLEDGE_BASE_DIR))
            md5 = _compute_md5(file_path)

            # 去重检查
            if md5 in existing_hashes:
                logger.info("跳过（已存在）: %s", rel_path)
                continue

            # 解析文档
            try:
                kb_name = _extract_knowledge_base(rel_path)
                chunks = parse_document(str(file_path))
            except Exception as e:
                logger.error("解析失败 %s: %s", rel_path, e)
                # 写入失败记录
                file_records.append(
                    KnowledgeDoc(
                        knowledge_base=_extract_knowledge_base(rel_path),
                        file_path=rel_path,
                        original_filename=file_path.name,
                        file_size=file_path.stat().st_size,
                        content_hash=md5,
                        status="failed",
                        error_message=str(e),
                    )
                )
                continue

            # 覆盖 metadata.source 为相对路径（替代原来的绝对路径）
            for chunk in chunks:
                chunk.metadata["source"] = rel_path
                chunk.metadata["kb_name"] = kb_name

            total_chunks.extend(chunks)
            total_new_files += 1

            # 先确保 KB 记录存在
            async with async_session() as db:
                kb = await _ensure_knowledge_base(db, kb_name)

            # 准备 MySQL 记录（先缓存，写入 Qdrant 后再持久化）
            file_records.append(
                KnowledgeDoc(
                    kb_id=kb.id,
                    knowledge_base=kb_name,
                    file_path=rel_path,
                    original_filename=file_path.name,
                    file_size=file_path.stat().st_size,
                    content_hash=md5,
                    status="processing",
                    chunk_count=len(chunks),
                )
            )

            logger.info("解析 %s → %d chunks", rel_path, len(chunks))

        # 6. 如果没有新文件，提前结束
        if not total_chunks:
            logger.info("没有新文件需要处理，所有文档已是最新。")
            return

        logger.info("新文件 %d 个，共 %d 个文档分块", total_new_files, len(total_chunks))

        # 7. 批量向量化
        logger.info("向量化中（共 %d 条）...", len(total_chunks))
        texts = [c.page_content for c in total_chunks]
        embeddings = await embed_batch(texts)
        logger.info("向量化完成")

        # 8. 写入 Qdrant
        vector_count = await upsert(total_chunks, embeddings)

        # 9. 更新 MySQL 记录
        async with async_session() as db:
            for rec in file_records:
                if rec.status == "processing":
                    rec.status = "ready"
                db.add(rec)
            await db.commit()

        elapsed = time.time() - start_time
        logger.info("=" * 50)
        logger.info("知识库初始化完成!")
        logger.info("  新处理文件: %d", total_new_files)
        logger.info("  写入向量数: %d", vector_count)
        logger.info("  MySQL 记录数: %d", len([r for r in file_records if r.status == "ready"]))
        logger.info("  总耗时: %.2fs", elapsed)
        logger.info("=" * 50)
    finally:
        # 关闭数据库连接池，防止事件循环关闭后 aiomysql 报错
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
