"""Agent Builder

构建 Agentic RAG 代理，将检索工具与 LLM 组合为自主决策的智能客服。
"""

import logging

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from app.core.config import settings

from .retrieval_tool import retrieve_knowledge

logger = logging.getLogger(__name__)

_llm: ChatOpenAI | None = None

SYSTEM_PROMPT = """你是一个专业的智能客服助手，专门回答关于用户提出的问题。

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


def build_agent():
    """构建 Agentic RAG 代理。

    Agent 拥有 retrieve_knowledge 工具，可自主判断是否需要检索知识库，
    结合检索结果回答用户问题。

    Returns:
        CompiledStateGraph: 可直接调用的 Agent 实例
    """
    llm = _get_llm()
    agent = create_agent(
        model=llm,
        tools=[retrieve_knowledge],
        system_prompt=SYSTEM_PROMPT
    )
    logger.info("Agent 构建完成 (model=%s, tools=%d)", settings.openai_model, 1)
    return agent
