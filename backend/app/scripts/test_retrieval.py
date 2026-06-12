"""检索测试脚本

交互式命令行工具，用于验证知识库检索效果。

使用方式:
    # 先初始化知识库
    python -m app.scripts.init_kb

    # 再运行测试
    python -m app.scripts.test_retrieval
"""

import asyncio
import logging

from app.services.embedding import embed
from app.services.vector_store import search
from app.utils.logging import setup_logging

setup_logging(level="WARNING")
logger = logging.getLogger(__name__)


def _print_result(results: list[dict]) -> None:
    """格式化打印检索结果。"""
    if not results:
        print("\n  [无匹配结果] 知识库中未找到相关内容。")
        return

    print(f"\n  {'='*60}")
    print(f"  找到 {len(results)} 条结果:")
    print(f"  {'='*60}")

    for i, r in enumerate(results, 1):
        source = r.get("source", "").split("/")
        filename = source[-1] if len(source) > 1 else source[0]
        section = r.get("section", "")
        subsection = r.get("subsection", "")

        title_parts = [f"#{i}"]
        if filename:
            title_parts.append(f"[{filename}]")
        if section:
            title_parts.append(section)
        if subsection:
            title_parts.append(f" > {subsection}")

        print(f"\n  {' | '.join(title_parts)}")
        print(f"  相关度: {r['score']}")
        print(f"  {'─'*60}")
        print(f"  {r.get('content', '')[:200]}")
        if len(r.get("content", "")) > 200:
            print("  ...")


async def main() -> None:
    """交互式检索测试。"""
    print("\n" + "=" * 60)
    print("  Auperator 知识库检索测试")
    print("=" * 60)
    print("  输入问题后查看检索结果")
    print("  输入 'exit' 或 'quit' 退出")
    print("=" * 60)

    while True:
        try:
            query = input("\n🔍 请输入问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not query:
            continue

        if query.lower() in ("exit", "quit"):
            break

        try:
            print("\n  正在检索...", end="", flush=True)
            query_vector = await embed(query)
            results = await search(query_vector, query_text=query)
            print("\r" + " " * 20 + "\r", end="")

            _print_result(results)

        except Exception as e:
            print(f"\n  [错误] 检索失败: {e}")

    print("\n再见!\n")


if __name__ == "__main__":
    asyncio.run(main())
