"""Agent Builder

构建 Agentic RAG 代理，将检索工具与 LLM 组合为自主决策的智能客服。
"""

import logging

from langchain.agents import create_agent
from langgraph.types import Checkpointer
from langchain_openai import ChatOpenAI

from app.core.config import settings

from .retrieval_tool import retrieve_knowledge

logger = logging.getLogger(__name__)

_llm: ChatOpenAI | None = None

SYSTEM_PROMPT_TEMPLATE = """你是一个专业的智能客服助手，专门回答关于用户提出的问题。

## 可用的知识库
{knowledge_base_section}

## 工作方式
你有以下工具可以使用：
- retrieve_knowledge: 从知识库中检索产品相关文档片段

当用户提问时，按照以下流程工作：
1. 判断问题类型：
   - 产品相关问题（功能、配置、故障排查等）→ 使用 retrieve_knowledge 工具检索
   - 问候、闲聊 → 直接回应，不需要检索
2. 检索后如果结果不够充分，可以换一种表述再次检索
3. 根据检索结果回答问题

## 回答要求
1. 仅根据知识库检索到的内容回答，不要编造信息
2. 回答时引用具体的文档名称和章节
3. 如果知识库中没有相关信息，说"抱歉，我暂时无法回答这个问题"
4. 回答应该专业、简洁、有条理
5. 检索到的知识片段与问题不相关时，不要强行使用"""

# 无知识库时的回退提示词
_FALLBACK_SYSTEM_PROMPT = """你是一个专业的智能客服助手，专门回答关于用户提出的问题。

## 工作方式
你有以下工具可以使用：
- retrieve_knowledge: 从知识库中检索产品相关文档片段

当用户提问时，按照以下流程工作：
1. 判断问题类型：
   - 产品相关问题（功能、配置、故障排查等）→ 使用 retrieve_knowledge 工具检索
   - 问候、闲聊 → 直接回应，不需要检索
2. 检索后如果结果不够充分，可以换一种表述再次检索
3. 根据检索结果回答问题

## 回答要求
1. 仅根据知识库检索到的内容回答，不要编造信息
2. 回答时引用具体的文档名称和章节
3. 如果知识库中没有相关信息，说"抱歉，我暂时无法回答这个问题"
4. 回答应该专业、简洁、有条理
5. 检索到的知识片段与问题不相关时，不要强行使用"""


def _get_llm() -> ChatOpenAI:
    """延迟初始化 LLM（单例）。"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        logger.info("初始化 LLM: %s", settings.openai_model)
    return _llm


async def _load_kb_list() -> list[dict]:
    """内部查询所有知识库信息。"""
    from app.core.database import async_session
    from app.services.knowledge import list_knowledge_bases

    async with async_session() as db:
        return await list_knowledge_bases(db)


def _format_kb_section(kb_list: list[dict]) -> str:
    """将知识库列表格式化为提示词中的文本段落。"""
    if not kb_list:
        return "当前没有可用的知识库。"

    lines = ["调用 retrieve_knowledge 工具时，可通过 kb_name 参数指定在特定知识库范围内检索："]
    for kb in kb_list:
        parts = [f"- **{kb['name']}**"]
        if kb.get("description"):
            parts.append(kb["description"])
        if kb.get("keywords"):
            parts.append(f"（关键词：{kb['keywords']}）")
        lines.append(" ".join(parts))

    names = ", ".join(kb["name"] for kb in kb_list)
    lines.append(f"\nkb_name 可选值：{names}（不填则检索全部知识库）")
    return "\n".join(lines)


async def build_agent(checkpointer: Checkpointer | None = None):
    """构建 Agentic RAG 代理。

    Agent 拥有 retrieve_knowledge 工具，可自主判断是否需要检索知识库，
    结合检索结果回答用户问题。创建 agent 时会自动查询当前知识库列表，
    将知识库信息注入提示词，使 agent 知道可检索的范围。

    Returns:
        CompiledStateGraph: 可直接调用的 Agent 实例
    """
    # 1. 查询知识库列表并构造提示词
    kb_list = await _load_kb_list()
    if kb_list:
        kb_section = _format_kb_section(kb_list)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(knowledge_base_section=kb_section)
    else:
        system_prompt = _FALLBACK_SYSTEM_PROMPT
        logger.info("无知识库，使用回退提示词")

    # 2. 构建 agent
    llm = _get_llm()
    agent = create_agent(
        model=llm,
        tools=[retrieve_knowledge],
        system_prompt=system_prompt,
        checkpointer=checkpointer
    )
    logger.info(
        "Agent 构建完成 (model=%s, tools=%d, kb_count=%d)",
        settings.openai_model, 1, len(kb_list),
    )
    return agent
