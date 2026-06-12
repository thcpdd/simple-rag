"""文档解析服务

统一的文档解析入口，按文件类型路由到不同的解析策略。
当前支持: .md, .txt
"""

from pathlib import Path

from langchain_core.documents import Document

from app.services.text_splitter import split_markdown, split_text


def parse_document(file_path: str) -> list[Document]:
    """解析文档并分块。

    根据文件扩展名自动选择解析策略：
    - .md: MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
    - .txt: RecursiveCharacterTextSplitter

    Args:
        file_path: 文档的绝对路径

    Returns:
        分块后的 Document 列表

    Raises:
        ValueError: 不支持的文件格式
        FileNotFoundError: 文件不存在
        IOError: 文件读取失败
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    ext = path.suffix.lower()
    text = path.read_text(encoding="utf-8")

    if ext == ".md":
        return split_markdown(text, source=str(path))
    elif ext == ".txt":
        return split_text(text, source=str(path))
    else:
        raise ValueError(f"不支持的文件格式: {ext}，仅支持 .md 和 .txt")
