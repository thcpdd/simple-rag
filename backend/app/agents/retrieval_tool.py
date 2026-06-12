"""检索 Tool（Agentic RAG 核心）

将文档检索包装为 LangChain Tool，供 Agent/LLM 自主调用。

设计思路（Agentic RAG vs 传统 RAG）:
- 传统 RAG: query → embed → search → 强制拼接 prompt → 调 LLM
- Agentic RAG: Tool 只负责 "检索并返回知识片段"，
  LLM 自主决定是否调用、何时调用、是否多次调用。
  这样可以避免无关问题也走检索流程，减少不必要的 API 调用。

使用方式:
    from app.services.retrieval_tool import retrieve_knowledge

    # 直接在代码中调用
    result = await retrieve_knowledge.ainvoke({"query": "你的问题"})

    # 或作为 Tool 传入 LangChain Agent
    agent = create_react_agent(llm, [retrieve_knowledge], ...)
"""

import logging

from langchain_core.documents import Document
from langchain_core.tools import tool

from app.services.embedding import embed
from app.services.vector_store import search

logger = logging.getLogger(__name__)

MAX_QUERY_LENGTH = 500


@tool
async def retrieve_knowledge(query: str) -> str:
    """当需要回答用户关于「Auperator 智能运维系统」产品的问题时，
    调用此工具从知识库中检索相关文档片段。

    如果调用后返回的结果不够充分，可以换一种问法再次调用。

    Args:
        query: 用户的原始问题或需要查询的关键词

    Returns:
        格式化的知识片段列表，包含文档名称、章节标题和原文摘要。
        如果没有找到相关内容，返回空字符串。
    """
    if not query or not query.strip():
        return ""

    query = query.strip()
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]
        logger.warning("查询超长，已截断至 %d 字", MAX_QUERY_LENGTH)

    # 1. 向量化查询
    logger.info("检索知识库: \"%s\"", query[:50])
    query_vector = await embed(query)

    # 2. 向量检索（top_k=5, score>=0.7）
    results = await search(query_vector)

    # 3. 检索为空
    if not results:
        logger.info("检索结果为空")
        return ""

    # 4. 格式化为可读文本
    formatted = _format_results(results)
    logger.info("检索到 %d 条结果", len(results))
    return formatted


def _format_results(results: list[dict]) -> str:
    """将检索结果格式化为 LLM 易读的文本。"""
    lines: list[str] = []
    for i, r in enumerate(results, 1):
        # 构建来源路径
        source_parts = []
        if r.get("source"):
            source_parts.append(r["source"])
        if r.get("section"):
            source_parts.append(f"> {r['section']}")
        if r.get("subsection"):
            source_parts.append(f"> {r['subsection']}")

        lines.append(f"[{i}] 来源: {' / '.join(source_parts)}")
        lines.append(f"    相关度: {r['score']}")
        lines.append(f"    内容: {r['content']}")
        lines.append("")

    return "\n".join(lines).strip()
