"""RAG 评估 Pipeline（Agentic RAG 模式）

对 test_dataset.json 中每个用例：
1. 运行 Agent（ainvoke），让 Agent 自主决定是否调用检索工具
2. 从 Agent 的对话历史中提取工具调用结果（ToolMessage）
3. 提取 Agent 的最终回答
4. 输出到 eval_results.json 供后续人工评估

设计原则：
- 不预先调用 embed/search，完全由 Agent 自主决定检索策略
- Agent 可能多次调用检索工具（换不同表述查询），所有调用结果都会被记录
"""

import asyncio
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from langchain_core.messages import ToolMessage

from app.agents.builder import build_agent
from app.core.database import engine

logging.getLogger("app").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.ERROR)
logging.getLogger("langgraph").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("qdrant_client").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


def _parse_tool_result(content: str) -> list[dict]:
    """解析 retrieve_knowledge 工具返回的格式化文本，提取结构化数据。

    输入格式（由 retrieval_tool._format_results 生成）:
        [1] 来源: doc_name / > section / > subsection
            相关度: 0.85
            内容: the content text

        [2] 来源: doc_name
            相关度: 0.75
            内容: the content text
    """
    chunks: list[dict] = []

    # 按 "[N]" 分割每个结果块
    raw_blocks = re.split(r'\n(?=\[\d+\])', content.strip())
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue

        # 提取来源行: "[1] 来源: ..."
        m = re.match(r'\[\d+\]\s+来源:\s*(.*)', block)
        if not m:
            continue
        source_raw = m.group(1).strip()

        # 解析来源: "doc_name / > section / > subsection"
        parts = [p.strip() for p in source_raw.split(" / ")]
        source = parts[0]
        section = parts[1].lstrip("> ").strip() if len(parts) > 1 else ""
        subsection = parts[2].lstrip("> ").strip() if len(parts) > 2 else ""

        # 提取相关度
        score = 0.0
        m = re.search(r'相关度:\s*([\d.]+)', block)
        if m:
            score = float(m.group(1))

        # 提取内容: "内容: " 之后的所有文本
        text = ""
        idx = block.find("内容: ")
        if idx != -1:
            text = block[idx + len("内容: "):].strip()

        chunks.append({
            "source": source,
            "section": section,
            "subsection": subsection,
            "content": text,
            "score": score,
        })

    return chunks


async def evaluate():
    test_path = os.path.join(os.path.dirname(__file__), "../../test_dataset.json")
    with open(test_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"加载 {len(test_cases)} 个测试用例\n")

    agent = await build_agent()
    results = []

    for i, case in enumerate(test_cases):
        question = case["question"]
        ground_truth = case["ground_truth"]

        print(f"{'='*70}")
        print(f"[{i+1}/{len(test_cases)}] {question[:70]}")
        print(f"{'='*70}")

        # ─── 运行 Agent（自主决策是否检索、检索几次） ───
        print("\n🤖 Agent 运行中...")
        try:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": question}]}
            )
            messages = result.get("messages", [])

            # 提取所有工具调用消息（Agent 可能多次调检索工具）
            tool_messages: list[str] = []
            for msg in messages:
                if isinstance(msg, ToolMessage):
                    tool_messages.append(msg.content if msg.content else "")

            print(f"  Agent 调用了 {len(tool_messages)} 次检索工具")

            # 解析工具调用中的检索结果
            all_chunks: list[dict] = []
            for j, tool_content in enumerate(tool_messages):
                if not tool_content:
                    continue
                parsed = _parse_tool_result(tool_content)
                all_chunks.extend(parsed)
                print(f"  第 {j+1} 次检索: {len(parsed)} 条结果")
                for k, ch in enumerate(parsed):
                    src = ch["source"]
                    score = ch["score"]
                    preview = ch["content"][:120].replace("\n", " ")
                    print(f"    [{k+1}] score={score:.4f} | {src}")
                    print(f"         {preview}")

            # 提取最终回答（最后一个非 ToolMessage 的消息）
            final_answer = ""
            for msg in reversed(messages):
                if hasattr(msg, "content") and not isinstance(msg, ToolMessage):
                    final_answer = msg.content or ""
                    break

            print(f"\n  最终回答 ({len(final_answer)} 字):")
            print(f"  {final_answer[:500]}")

        except Exception as e:
            print(f"  ❌ Agent 异常: {e}")
            all_chunks = []
            final_answer = f"[ERROR] {e}"
            tool_messages = []

        results.append({
            "index": i + 1,
            "question": question,
            "ground_truth": ground_truth,
            "ideal_contexts": case.get("retrieved_contexts", []),
            "agent_tool_calls": len(tool_messages),
            "agent_retrieval": all_chunks,
            "agent_answer": final_answer,
        })
        print()

    output_path = os.path.join(os.path.dirname(__file__), "../../evals/eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 运行结果已保存到: {output_path}")


async def main():
    try:
        await evaluate()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
