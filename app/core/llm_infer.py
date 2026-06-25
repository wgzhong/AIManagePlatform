"""
LLM 推理模块 — 向后兼容的薄封装层。

⚠️ 本模块已按职责拆分为三个子模块（详见第三阶段 F4 重构）：
    - :mod:`app.core.llm_client`  — HTTP 客户端管理（连接池/预热/心跳）
    - :mod:`app.core.llm_stream`  — 流式请求处理（SSE 解析/重试）
    - :mod:`app.core.llm_health`  — 健康检查

本文件保留以下向后兼容入口，外部调用方无需改动：
    - ``LLMInfer`` 类（含 warmup / close / stream_chat_request / check_health）
    - ``llm_infer`` 全局单例
    - ``stream_chat_request`` 模块级异步生成器函数

新代码请直接引用子模块。
"""

import logging
from typing import Any, AsyncGenerator, List, Tuple

from .llm_client import llm_client, LLMHttpClient
from .llm_stream import llm_streamer, LLMStreamer
from .llm_health import check_health as _check_health

logger = logging.getLogger("LLM")


class LLMInfer:
    """LLM 推理客户端类（向后兼容封装）。

    实际逻辑已拆分到 LLMHttpClient / LLMStreamer / llm_health 模块。
    本类只做委托，保留旧代码 ``from app.core.llm_infer import llm_infer`` 的兼容性。
    """

    def __init__(self):
        # 暴露拆分后的子模块实例，便于旧代码访问属性
        self._client: LLMHttpClient = llm_client
        self._streamer: LLMStreamer = llm_streamer

    # ------------------------------------------------------------------
    # 调试相关（旧代码可能直接访问 _debug_mode / _debug_log）
    # ------------------------------------------------------------------
    @property
    def _debug_mode(self) -> bool:
        return self._client.debug_mode

    def _debug_log(self, msg: str) -> None:
        self._client.debug_log(msg)

    def _get_client(self):
        """旧代码兼容：返回内部 httpx.AsyncClient"""
        return self._client.get_client()

    def _log_connection_stats(self) -> None:
        self._client._log_connection_stats()

    @staticmethod
    def _fast_json_dumps(obj) -> bytes:
        return LLMHttpClient.fast_json_dumps(obj)

    @staticmethod
    def _build_payload_bytes(payload: dict) -> bytes:
        return LLMHttpClient.fast_json_dumps(payload)

    # ------------------------------------------------------------------
    # 预热 / 关闭
    # ------------------------------------------------------------------
    async def warmup(self, api_url: str, api_key: str = None) -> None:
        await self._client.warmup(api_url, api_key)

    async def close(self) -> None:
        await self._client.close()

    # ------------------------------------------------------------------
    # 流式请求
    # ------------------------------------------------------------------
    async def stream_chat_request(
        self,
        messages: list,
        api_key: str,
        api_url: str,
        tools: List[dict] = None,
        tool_choice: Any = None,  # 新增
        model: str = "glm-4.6v",
        max_tokens: int = 1024,
        temperature: float = 1.0,
        top_p: float = 0.95,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        thinking_enabled: bool = False,
        max_retries: int = 2,
    ) -> AsyncGenerator[Tuple[str, Any, Any], None]:
        async for result in self._streamer.stream_chat_request(
            messages=messages,
            api_key=api_key,
            api_url=api_url,
            tools=tools,
            tool_choice=tool_choice,  # 透传
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            thinking_enabled=thinking_enabled,
            max_retries=max_retries,
        ):
            yield result

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------
    async def check_health(self) -> dict:
        return await _check_health()


# 向后兼容：全局单例
llm_infer = LLMInfer()


async def stream_chat_request(
    messages: list,
    api_key: str,
    api_url: str,
    tools: List[dict] = None,
    tool_choice: Any = None,  # 新增
    model: str = "glm-4.6v",
    max_tokens: int = 1024,
    temperature: float = 1.0,
    top_p: float = 0.95,
    frequency_penalty: float = 0,
    presence_penalty: float = 0,
    thinking_enabled: bool = False,
    max_retries: int = 2,
) -> AsyncGenerator[Tuple[str, Any, Any], None]:
    """向后兼容的流式请求接口（异步生成器）。

    调用 LLMStreamer.stream_chat_request。
    """
    async for result in llm_streamer.stream_chat_request(
        messages=messages,
        api_key=api_key,
        api_url=api_url,
        tools=tools,
        tool_choice=tool_choice,  # 透传
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        thinking_enabled=thinking_enabled,
        max_retries=max_retries,
    ):
        yield result
