from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseDeleteResponse,
    KnowledgeBaseItem,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    KnowledgeDocResponse,
    KnowledgeListResponse,
)
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])

# 文件上传限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".md", ".txt"}

# 知识库根目录
KNOWLEDGE_BASE_DIR = settings.knowledge_base_path


# ─── KnowledgeBase CRUD ───


@router.get("/bases", response_model=KnowledgeBaseListResponse)
async def list_bases(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取所有知识库列表及其文档数量（含描述、关键词等元信息）。"""
    items = await knowledge_service.list_knowledge_bases(db)
    return KnowledgeBaseListResponse(
        total=len(items),
        items=[KnowledgeBaseItem(name=i["name"], doc_count=i["doc_count"]) for i in items],
    )


@router.get("/bases/detail", response_model=list[KnowledgeBaseResponse])
async def list_bases_detail(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取所有知识库的详细信息（含描述、关键词、文档数量等）。"""
    items = await knowledge_service.list_knowledge_bases(db)
    return [KnowledgeBaseResponse(**i) for i in items]


@router.get("/bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取单个知识库详情。"""
    kb = await knowledge_service.get_knowledge_base(db, kb_id)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    # 查询文档数量
    docs = await knowledge_service.list_docs(db, kb_id=kb_id)
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        keywords=kb.keywords,
        doc_count=len(docs),
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=201)
async def create_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """创建知识库（名称必须唯一）。"""
    # 检查名称是否已存在
    existing = await knowledge_service.get_knowledge_base_by_name(db, data.name.strip())
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"知识库「{data.name}」已存在",
        )

    kb = await knowledge_service.create_knowledge_base(db, data)

    # 创建对应的磁盘目录
    kb_dir = KNOWLEDGE_BASE_DIR / kb.name
    kb_dir.mkdir(parents=True, exist_ok=True)

    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        keywords=kb.keywords,
        doc_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.put("/bases/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """更新知识库元信息。"""
    # 如果重命名，检查新名称是否已存在
    if data.name:
        existing = await knowledge_service.get_knowledge_base_by_name(db, data.name.strip())
        if existing and existing.id != kb_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"知识库「{data.name}」已存在",
            )

    kb = await knowledge_service.update_knowledge_base(db, kb_id, data)
    if kb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    docs = await knowledge_service.list_docs(db, kb_id=kb_id)
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        keywords=kb.keywords,
        doc_count=len(docs),
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.delete("/bases/{kb_id}", response_model=KnowledgeBaseDeleteResponse)
async def delete_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """级联删除知识库：删除所有文档的向量、磁盘文件、DB 记录。"""
    result = await knowledge_service.delete_knowledge_base(db, kb_id)
    if result["deleted_docs"] == 0:
        # 检查 KB 是否存在
        kb = await knowledge_service.get_knowledge_base(db, kb_id)
        if kb is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识库不存在")

    return KnowledgeBaseDeleteResponse(
        message="知识库已删除",
        deleted_docs=result["deleted_docs"],
    )


# ─── Document CRUD ───


@router.get("/list", response_model=KnowledgeListResponse)
async def list_docs(
    knowledge_base: str | None = None,
    kb_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取知识库文档列表。可通过 knowledge_base 或 kb_id 参数筛选。"""
    docs = await knowledge_service.list_docs(db, knowledge_base=knowledge_base, kb_id=kb_id)
    return KnowledgeListResponse(
        total=len(docs),
        items=[KnowledgeDocResponse.model_validate(d) for d in docs],
    )


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
async def get_doc(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取单个知识库文档详情。"""
    doc = await knowledge_service.get_doc(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    return doc


@router.post("/upload", response_model=KnowledgeDocResponse, status_code=202)
async def upload_doc(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    kb_id: int = Form(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """上传知识库文档（支持 .md / .txt）。后台异步处理，立即返回。

    Args:
        file: 上传的文件
        kb_id: 知识库 ID（必须已存在）
    """
    # 1. 校验文件类型
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. 校验知识库是否存在
    kb = await knowledge_service.get_knowledge_base(db, kb_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在",
        )

    # 3. 读取文件内容，校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）",
        )

    # 4. 自动创建知识库目录并保存文件
    kb_dir = KNOWLEDGE_BASE_DIR / kb.name
    kb_dir.mkdir(parents=True, exist_ok=True)

    # 处理文件名冲突
    save_path = kb_dir / (file.filename or "upload")
    if save_path.exists():
        # 如果已存在同名文件，添加时间戳后缀
        stem = save_path.stem
        suffix = save_path.suffix
        import time

        save_path = kb_dir / f"{stem}_{int(time.time())}{suffix}"

    save_path.write_bytes(content)

    # 5. 创建初始记录（状态：processing）
    doc = await knowledge_service.create_doc_record(db, save_path, kb.id, kb.name)

    # 6. 后台处理文档（解析 → 向量化 → 写入 Qdrant → 更新状态）
    background_tasks.add_task(
        knowledge_service.process_document_background, doc.id, save_path
    )

    return doc


@router.delete("/{doc_id}", status_code=204)
async def delete_doc(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """删除知识库文档（同时删除 Qdrant 向量和 MySQL 记录）。"""
    doc = await knowledge_service.get_doc(db, doc_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")

    await knowledge_service.delete_document(db, doc)
