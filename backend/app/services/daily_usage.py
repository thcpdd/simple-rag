"""每日调用频率限制服务

使用全局 dict 记录每个用户当天的调用次数，跨天自动重置。
定期持久化到本地文件，服务重启后恢复数据，最多丢失 5 次计数。
"""

import asyncio
import json
import logging
from datetime import date, datetime
from pathlib import Path

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# 持久化文件路径：backend/data/daily_usage.json
_DATA_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "daily_usage.json"

# 全局计数器：user_id -> (today_date, call_count)
_daily_usage: dict[int, tuple[date, int]] = {}
# 每用户一把锁，避免并发请求导致计数不准确
_user_locks: dict[int, asyncio.Lock] = {}


def _load_from_disk() -> dict[int, tuple[date, int]]:
    """从磁盘 JSON 文件加载今日的调用计数，旧数据自动跳过。"""
    today = date.today()
    result: dict[int, tuple[date, int]] = {}

    if not _DATA_FILE.exists():
        return result

    try:
        raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        for item in raw:
            uid = item["user_id"]
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            if d == today:
                result[uid] = (d, item["count"])
        logger.info("从 %s 恢复 %d 条今日调用计数", _DATA_FILE, len(result))
    except Exception:
        logger.warning("读取调用计数文件失败，将从头开始计数", exc_info=True)

    return result


def _save_to_disk() -> None:
    """将当前所有用户的计数写回磁盘 JSON 文件。"""
    data = [
        {"user_id": uid, "date": d.isoformat(), "count": c}
        for uid, (d, c) in _daily_usage.items()
    ]
    try:
        _DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DATA_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        logger.warning("持久化调用计数失败", exc_info=True)


# 模块加载时恢复上次保存的数据
_daily_usage.update(_load_from_disk())


async def check_and_increment(user_id: int, limit: int) -> None:
    """检查并递增用户当日调用次数。

    如果当日调用次数未超限则递增并返回；
    如果超限则抛出 HTTP 429 异常。
    每 5 次调用自动持久化一次。
    """
    # 获取该用户的锁，不阻塞其他用户
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    lock = _user_locks[user_id]

    async with lock:
        today = date.today()
        record = _daily_usage.get(user_id)

        if record is None or record[0] != today:
            # 首次调用或跨天：重置计数器
            _daily_usage[user_id] = (today, 1)
            logger.debug("用户 %d 首次调用（或跨天）：count=1", user_id)
            return

        _, count = record
        if count >= limit:
            logger.warning(
                "用户 %d 今日调用次数已超限：count=%d, limit=%d",
                user_id, count, limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"今日对话次数已用尽（{limit} 次），请明天再试",
            )

        new_count = count + 1
        _daily_usage[user_id] = (today, new_count)
        logger.debug("用户 %d 调用递增：count=%d", user_id, new_count)

        # 每 5 次持久化一次，宕机最多丢 4 次计数
        if new_count % 5 == 0:
            _save_to_disk()
