"""
统计管理模块
负责管理系统统计数据的存储和查询。

性能优化：内存累加 + 后台线程定时落盘（默认 30 秒），
避免每次请求都全量读写 JSON 文件导致的磁盘 IO 与锁竞争。
崩溃时最多丢失一个落盘周期内的统计。
"""

import json
import os
import threading
import logging
from datetime import datetime
from typing import Dict, Any

from .config import settings

logger = logging.getLogger("STATS")

# 落盘周期（秒）
FLUSH_INTERVAL = 30.0


class StatsManager:
    """统计管理器类（内存累加 + 定时落盘）"""

    def __init__(self):
        """初始化统计管理器，加载历史数据到内存"""
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = self._load_from_disk()
        self._dirty = False
        self._running = False
        self._flush_thread: threading.Thread = None

    # ---------- 内部：磁盘读写 ----------
    def _load_from_disk(self) -> Dict[str, Any]:
        """从文件加载统计数据"""
        if os.path.exists(settings.stats_file):
            try:
                with open(settings.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("加载统计数据失败: %s", e)
        return {
            "daily_requests": 0,
            "total_requests": 0,
            "today_input_tokens": 0,
            "today_output_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "tool_calls": {"get_time": 0, "calculate": 0, "read_file": 0, "total": 0},
            "daily_records": [],
            "last_reset": datetime.now().date().isoformat(),
        }

    def _save_to_disk(self) -> None:
        """把内存中的统计数据写入文件"""
        with self._lock:
            snapshot = json.loads(json.dumps(self._stats, ensure_ascii=False))
        try:
            with open(settings.stats_file, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("统计落盘失败: %s", e)

    def _rollover_if_new_day(self, stats: Dict[str, Any]) -> None:
        """跨天时重置每日计数（调用方需持锁）"""
        today = datetime.now().date().isoformat()
        if stats.get("last_reset") != today:
            stats["daily_requests"] = 0
            stats["today_output_tokens"] = 0
            stats["today_input_tokens"] = 0
            stats["last_reset"] = today

    # ---------- 后台落盘线程 ----------
    def start(self):
        """启动定时落盘线程"""
        if self._running:
            return
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()
        logger.info("统计落盘线程已启动，周期 %.0fs", FLUSH_INTERVAL)

    def stop(self):
        """停止线程并立即把脏数据落盘"""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=2)
        if self._dirty:
            self._save_to_disk()
            self._dirty = False

    def _flush_loop(self):
        import time
        while self._running:
            time.sleep(FLUSH_INTERVAL)
            if self._dirty:
                self._save_to_disk()
                with self._lock:
                    self._dirty = False

    # ---------- 对外接口（签名保持兼容）----------
    def load_stats(self) -> Dict[str, Any]:
        """获取当前统计数据（返回内存快照的拷贝）"""
        with self._lock:
            return json.loads(json.dumps(self._stats, ensure_ascii=False))

    def save_stats(self, stats: Dict[str, Any]) -> None:
        """整体替换内存统计并立即落盘"""
        with self._lock:
            self._stats = stats
            self._dirty = True
        self._save_to_disk()
        with self._lock:
            self._dirty = False

    def increment_request_count(self) -> None:
        """增加请求计数"""
        with self._lock:
            self._rollover_if_new_day(self._stats)
            today = self._stats["last_reset"]
            self._stats["daily_requests"] += 1
            self._stats["total_requests"] += 1

            found = False
            for record in self._stats["daily_records"]:
                if record["date"] == today:
                    record["count"] += 1
                    found = True
                    break
            if not found:
                self._stats["daily_records"].append({"date": today, "count": 1})
            self._dirty = True

    def update_token_usage(self, output_tokens: int, input_tokens: int = 0) -> None:
        """更新 Token 使用统计"""
        with self._lock:
            self._rollover_if_new_day(self._stats)
            self._stats["today_output_tokens"] = self._stats.get("today_output_tokens", 0) + output_tokens
            self._stats["total_output_tokens"] = self._stats.get("total_output_tokens", 0) + output_tokens
            self._stats["today_input_tokens"] = self._stats.get("today_input_tokens", 0) + input_tokens
            self._stats["total_input_tokens"] = self._stats.get("total_input_tokens", 0) + input_tokens
            self._dirty = True

    def increment_tool_call(self, tool_name: str) -> None:
        """增加工具调用计数（工具不存在时自动初始化）"""
        with self._lock:
            tool_calls = self._stats.setdefault("tool_calls", {})
            tool_calls[tool_name] = tool_calls.get(tool_name, 0) + 1
            tool_calls["total"] = tool_calls.get("total", 0) + 1
            self._dirty = True


stats_manager = StatsManager()
