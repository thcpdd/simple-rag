from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.knowledge import KnowledgeDocResponse, KnowledgeListResponse
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["知识库"])

# 文件上传限制
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".md", ".txt"}

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "knowledges" / "uploads"


@router.get("/list", response_model=KnowledgeListResponse)
async def list_docs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """获取知识库文档列表。"""
    docs = await knowledge_service.list_docs(db)
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
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """上传知识库文档（支持 .md / .txt）。后台异步处理，立即返回。"""
    # 1. 校验文件类型
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. 读取文件内容，校验大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件过大（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）",
        )

    # 3. 保存到 uploads 目录
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / (file.filename or "upload")
    save_path.write_bytes(content)

    # 4. 创建初始记录（状态：processing）
    doc = await knowledge_service.create_doc_record(db, save_path)

    # 5. 后台处理文档（解析 → 向量化 → 写入 Qdrant → 更新状态）
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
