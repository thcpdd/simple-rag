"""文档分块服务

支持 .md 和 .txt 文件的智能分块：
- .md: 按 Markdown 标题（## / ###）分组，长段落二次切分
- .txt: 纯按字符长度切分
"""

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# Markdown 标题层级：按 ## 和 ### 分组
HEADERS_TO_SPLIT_ON = [
    ("##", "section"),
    ("###", "subsection"),
]

# 文本二次切分参数
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def _create_markdown_splitter() -> MarkdownHeaderTextSplitter:
    """创建 Markdown 标题分组器。"""
    return MarkdownHeaderTextSplitter(
        headers_to_split_on=HEADERS_TO_SPLIT_ON,
        return_each_line=False,
    )


def _create_text_splitter() -> RecursiveCharacterTextSplitter:
    """创建纯文本长度切分器。"""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )


def split_markdown(text: str, source: str = "") -> list[Document]:
    """对 Markdown 文本进行分块。

    策略：先按标题分组，再对过长的子段做二次切分，
    保证每个 chunk 的 metadata 中包含章节信息。

    Args:
        text: Markdown 原文
        source: 来源文件路径，会写入每个 chunk 的 metadata

    Returns:
        分块后的 Document 列表
    """
    md_splitter = _create_markdown_splitter()
    text_splitter = _create_text_splitter()

    # 第一步：按标题分组
    sections = md_splitter.split_text(text)

    # 第二步：对每个 section，如果内容过长则二次切分
    chunks: list[Document] = []
    for doc in sections:
        if len(doc.page_content) <= CHUNK_SIZE:
            # 内容不长，直接保留
            doc.metadata["source"] = source
            chunks.append(doc)
        else:
            # 内容过长，二次切分，保留父级标题 metadata
            sub_chunks = text_splitter.split_documents([doc])
            for sub in sub_chunks:
                sub.metadata["source"] = source
                chunks.append(sub)

    return chunks


def split_text(text: str, source: str = "") -> list[Document]:
    """对纯文本进行分块。

    无标题结构，直接按字符长度切分。

    Args:
        text: 纯文本
        source: 来源文件路径

    Returns:
        分块后的 Document 列表
    """
    text_splitter = _create_text_splitter()
    docs = text_splitter.create_documents([text])
    for doc in docs:
        doc.metadata["source"] = source
    return docs
