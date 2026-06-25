"""
LLM HTTP 客户端管理模块。

职责：
- 管理 httpx.AsyncClient 单例（连接池复用、HTTP/2、SSL 配置）
- 连接预热（warmup）：首次请求前建立真实连接以降低首包延迟
- 心跳保活（heartbeat）：空闲时定期发请求，保持连接活跃

从原 llm_infer.py 拆分（详见第三阶段 F4 重构）。
"""

import asyncio
import json
import logging
import time
from typing import Optional

import httpx
from httpx import AsyncHTTPTransport

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None

from .config import settings

logger = logging.getLogger("LLM")


# 模块级常量（原 LLMInfer 类属性）
LIMITS = httpx.Limits(
    max_connections=100,
    max_keepalive_connections=20,
    keepalive_expiry=60.0,
)
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
HEARTBEAT_INTERVAL = 30.0


class LLMHttpClient:
    """LLM HTTP 客户端：连接池管理、预热、心跳保活。

    通过 :meth:`get_client` 复用连接，避免每次请求重新握手。
    """

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._warmup_done = False
        self._debug_mode = settings.llm_debug
        self._connection_count = 0
        self._reuse_count = 0
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._last_request_time = 0.0
        self._api_url: Optional[str] = None
        self._api_key: Optional[str] = None
        # SSL 校验开关：生产默认开启，本地调试可经 LLM_VERIFY_SSL=false 关闭
        self._verify_ssl = settings.llm_verify_ssl
        # SSL/TLS 会话缓存，复用 SSL 握手
        self.TRANSPORT = AsyncHTTPTransport(
            retries=0,
            http2=True,
            verify=self._verify_ssl,
        )

    # ------------------------------------------------------------------
    # 日志与诊断
    # ------------------------------------------------------------------
    def debug_log(self, msg: str) -> None:
        """调试日志输出（使用 INFO 级别确保在默认配置下可见）"""
        if self._debug_mode:
            logger.info(msg)

    def _log_connection_stats(self) -> None:
        """记录连接池统计信息"""
        try:
            if self._client and hasattr(self._client, '_transport'):
                transport = getattr(self._client, '_transport', None)
                if transport and hasattr(transport, '_pool'):
                    pool = getattr(transport, '_pool', None)
                    if pool:
                        active = getattr(pool, '_connections_active', 'N/A')
                        idle = getattr(pool, '_connections_idle', 'N/A')
                        self.debug_log(f"连接池状态 - 活跃连接: {active}, 空闲连接: {idle}")
        except Exception as e:
            self.debug_log(f"连接池状态获取失败: {type(e).__name__}")

    # ------------------------------------------------------------------
    # 客户端获取
    # ------------------------------------------------------------------
    def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端，复用连接以提高性能"""
        if self._client is None:
            start_time = time.time()
            self._client = httpx.AsyncClient(
                transport=self.TRANSPORT,
                limits=LIMITS,
                timeout=TIMEOUT,
                headers={"User-Agent": "AIManagePlatform/1.0"},
                follow_redirects=False,
                verify=self._verify_ssl,
                trust_env=False,
            )
            init_ms = (time.time() - start_time) * 1000
            self.debug_log(f"HTTP客户端初始化耗时: {init_ms:.2f}ms")
            self.debug_log("HTTP/2 模式: 已启用 | SSL会话缓存: 已启用")
        else:
            self.debug_log("HTTP客户端复用成功，已存在实例")
        return self._client

    @property
    def debug_mode(self) -> bool:
        return self._debug_mode

    @property
    def last_request_time(self) -> float:
        return self._last_request_time

    @last_request_time.setter
    def last_request_time(self, value: float) -> None:
        self._last_request_time = value

    # ------------------------------------------------------------------
    # 序列化辅助（orjson 优先，回退 stdlib）
    # ------------------------------------------------------------------
    @staticmethod
    def fast_json_dumps(obj) -> bytes:
        """快速 JSON 序列化，优先使用 orjson"""
        if HAS_ORJSON:
            return orjson.dumps(obj)
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")

    # ------------------------------------------------------------------
    # 预热
    # ------------------------------------------------------------------
    async def warmup(self, api_url: str, api_key: str = None) -> None:
        """预热 HTTP 连接，发送真实请求建立并保持连接。

        Args:
            api_url: API 地址
            api_key: 可选的 API Key，用于发送真实请求
        """
        if self._warmup_done:
            return

        self._api_url = api_url
        self._api_key = api_key

        client = self.get_client()

        warmup_payload = {
            "model": settings.llm_default_model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }

        warmup_headers = {"Content-Type": "application/json"}
        if api_key:
            warmup_headers["Authorization"] = f"Bearer {api_key}"

        try:
            start_time = time.time()
            response = await client.post(
                api_url,
                json=warmup_payload,
                headers=warmup_headers,
                timeout=15.0,
            )
            elapsed = (time.time() - start_time) * 1000
            self.debug_log(
                f"连接预热完成，耗时: {elapsed:.2f}ms | 状态码: {response.status_code}"
            )
            self._warmup_done = True
            self._last_request_time = time.time()

            if api_key:
                self._start_heartbeat()

        except Exception as e:
            self.debug_log(f"预热失败: {str(e)[:80]}")
            # 即使失败也标记为已完成，避免反复预热
            self._warmup_done = True

    # ------------------------------------------------------------------
    # 心跳保活
    # ------------------------------------------------------------------
    def _start_heartbeat(self) -> None:
        """启动心跳保活任务"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.debug_log(f"心跳保活任务已启动，间隔: {HEARTBEAT_INTERVAL}s")

    async def _heartbeat_loop(self) -> None:
        """心跳保活循环，定期发送请求保持连接活跃"""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)

                idle_time = time.time() - self._last_request_time
                if idle_time > HEARTBEAT_INTERVAL and self._api_url and self._api_key:
                    self.debug_log(f"发送心跳保活请求... (空闲: {idle_time:.0f}s)")

                    client = self.get_client()
                    heartbeat_payload = {
                        "model": settings.llm_default_model,
                        "messages": [{"role": "user", "content": "heartbeat"}],
                        "max_tokens": 1,
                        "stream": False,
                    }
                    heartbeat_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}",
                    }

                    start_time = time.time()
                    response = await client.post(
                        self._api_url,
                        json=heartbeat_payload,
                        headers=heartbeat_headers,
                        timeout=10.0,
                    )
                    elapsed = (time.time() - start_time) * 1000

                    if elapsed < 100:
                        self.debug_log(f"✅ 心跳成功，连接复用！耗时: {elapsed:.2f}ms")
                    else:
                        self.debug_log(
                            f"心跳完成，耗时: {elapsed:.2f}ms | 状态: {response.status_code}"
                        )

                    self._last_request_time = time.time()

            except asyncio.CancelledError:
                self.debug_log("心跳任务已取消")
                break
            except Exception as e:
                self.debug_log(f"心跳失败: {str(e)[:50]}")
                # 继续尝试，不中断心跳循环

    # ------------------------------------------------------------------
    # 关闭
    # ------------------------------------------------------------------
    async def close(self) -> None:
        """关闭 HTTP 客户端连接"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._client:
            await self._client.aclose()
            self._client = None
            self.debug_log("HTTP客户端已关闭")


# 模块级单例
llm_client = LLMHttpClient()
