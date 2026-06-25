"""
LLM 流式请求模块。

职责：
- 构建 payload 并发送流式 chat 请求
- 解析 SSE 数据流（aiter_lines）
- 消息截断、首包统计、重试逻辑
- 暴露 stream_chat_request 异步生成器入口

从原 llm_infer.py 拆分（详见第三阶段 F4 重构）。
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from .llm_client import llm_client, LLMHttpClient
from .config import settings

logger = logging.getLogger("LLM")


class LLMStreamer:
    """流式 chat 请求处理器：SSE 解析 + 网络错误重试。"""

    def __init__(self, client: LLMHttpClient):
        self._client = client

    # ------------------------------------------------------------------
    # 消息预处理
    # ------------------------------------------------------------------
    @staticmethod
    def _truncate_messages(messages: List[dict], max_messages: int = 20) -> List[dict]:
        """智能截断历史消息，保留 system + 最近 N 条"""
        if len(messages) <= max_messages:
            return messages

        result = []
        for m in messages:
            if m.get("role") == "system":
                result.append(m)
                break

        remaining = max_messages - len(result)
        result.extend(messages[-remaining:])

        client = llm_client
        client.debug_log(f"消息截断: {len(messages)} -> {len(result)} 条")
        return result

    @staticmethod
    def _estimate_messages_size(messages: List[dict]) -> int:
        """估算 messages 总体大小（字符数）"""
        return sum(len(str(m.get("content", ""))) for m in messages)

    # ------------------------------------------------------------------
    # 流式请求入口
    # ------------------------------------------------------------------
    async def stream_chat_request(
        self,
        messages: list,
        api_key: str,
        api_url: str,
        tools: List[dict] = None,
        tool_choice: Optional[Any] = None,  # 新增：覆盖默认 tool_choice
        model: str = "glm-4.6v",
        max_tokens: int = 1024,
        temperature: float = 1.0,
        top_p: float = 0.95,
        frequency_penalty: float = 0,
        presence_penalty: float = 0,
        thinking_enabled: bool = False,
        max_retries: int = 2,
    ) -> AsyncGenerator[Tuple[str, Any, Any], None]:
        """发送流式请求，使用 aiter_lines() 处理 SSE 流。

        对连接级网络错误自动重试（最多 max_retries 次），
        一旦开始接收流数据则不再重试。

        异步生成器，逐个 yield (content_text, tool_calls_chunk, usage)。
        """
        request_start_time = time.time()
        total_content_chars = 0
        chunk_count = 0
        first_chunk_time: Optional[float] = None

        attempt = 0
        while True:
            attempt += 1
            try:
                async for content, tool_calls, usage in self._attempt_stream(
                    messages=messages,
                    api_key=api_key,
                    api_url=api_url,
                    tools=tools,
                    tool_choice=tool_choice,  # 传递覆盖值
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    frequency_penalty=frequency_penalty,
                    presence_penalty=presence_penalty,
                    thinking_enabled=thinking_enabled,
                    counter={
                        "content": total_content_chars,
                        "chunks": chunk_count,
                        "first_chunk": first_chunk_time,
                    },
                ):
                    if isinstance(content, str) and content:
                        total_content_chars += len(content)
                    chunk_count += 1
                    yield content, tool_calls, usage
                break  # 正常完成，退出重试循环
            except (
                httpx.ConnectError,
                httpx.ReadError,
                httpx.RemoteProtocolError,
                httpx.PoolTimeout,
            ) as e:
                if attempt > max_retries:
                    self._client.debug_log(
                        f"重试已达上限({max_retries})，抛出错误: {type(e).__name__}: {e}"
                    )
                    raise
                wait = min(0.5 * attempt, 2.0)
                self._client.debug_log(
                    f"网络错误 {type(e).__name__}，第 {attempt} 次重试，等待 {wait}s"
                )
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError:
                # HTTP 业务错误（4xx/5xx）不重试，直接向上抛
                raise

        total_elapsed = (time.time() - request_start_time) * 1000
        self._client.debug_log("===== 请求完成 =====")
        self._client.debug_log(
            f"总耗时: {total_elapsed:.2f}ms | 数据块数: {chunk_count} | 输出字符: {total_content_chars}"
        )
        if first_chunk_time:
            self._client.debug_log(
                f"首包延迟: {first_chunk_time:.2f}ms | 后续传输: {(total_elapsed - first_chunk_time):.2f}ms"
            )

    # ------------------------------------------------------------------
    # 单次流式请求尝试
    # ------------------------------------------------------------------
    async def _attempt_stream(
        self,
        messages,
        api_key,
        api_url,
        tools,
        tool_choice=None,  # 新增参数
        model=None,
        max_tokens=None,
        temperature=None,
        top_p=None,
        frequency_penalty=None,
        presence_penalty=None,
        thinking_enabled=None,
        counter: Dict[str, Any] = None,
    ) -> AsyncGenerator[Tuple[str, Any, Any], None]:
        """单次流式请求尝试。counter 用于跨重试统计（dict 引用）。"""
        client = self._client

        # 智能截断过长历史，避免 payload 膨胀
        client.debug_log(f"API key 长度: {len(api_key)} 字符")
        truncated_messages = self._truncate_messages(messages, max_messages=20)
        msg_size = self._estimate_messages_size(truncated_messages)
        client.debug_log(f"model = {model}")

        payload = {
            "model": model,
            "messages": truncated_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"},
        }

        if tools:
            payload["tools"] = tools
            # 使用传入的 tool_choice 覆盖值，未传则默认 "auto"
            payload["tool_choice"] = tool_choice if tool_choice is not None else "auto"
        
        # ===== DEBUG: 打印工具相关 payload 完整内容 =====
        client.debug_log(f"[DEBUG-PAYLOAD] tool_choice 原始值: {tool_choice}")
        client.debug_log(f"[DEBUG-PAYLOAD] payload['tool_choice'] 最终值: {payload.get('tool_choice')}")
        if tools:
            client.debug_log(f"[DEBUG-PAYLOAD] tools 数量: {len(tools)}")
            for i, t in enumerate(tools):
                client.debug_log(f"[DEBUG-PAYLOAD]   tools[{i}].function.name = {t.get('function', {}).get('name', '?')}")
        else:
            client.debug_log("[DEBUG-PAYLOAD] ⚠️ tools 为空!")

        # 使用 orjson 预序列化 payload 为字节，避免 httpx 内部重复序列化
        serialize_start = time.time()
        payload_bytes = client.fast_json_dumps(payload)
        serialize_elapsed = (time.time() - serialize_start) * 1000
        payload_size_kb = len(payload_bytes) / 1024

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Content-Length": str(len(payload_bytes)),
        }

        http_client = client.get_client()

        client.debug_log("===== 请求开始 =====")
        client.debug_log(
            f"消息数: {len(truncated_messages)}/{len(messages)} | 估算大小: {msg_size} 字符 | payload: {payload_size_kb:.1f}KB"
        )
        client.debug_log(f"序列化耗时: {serialize_elapsed:.2f}ms")
        client.debug_log(f"温度: {temperature} | top_p: {top_p}")
        client.debug_log(f"启用工具: {len(tools) if tools else 0} 个")
        client._log_connection_stats()

        connect_start = time.time()
        client.debug_log("开始建立HTTP连接...")
        client.debug_log(f"目标URL: {api_url}")

        async with http_client.stream(
            "POST",
            api_url,
            content=payload_bytes,
            headers=headers,
        ) as response:
            connect_elapsed = (time.time() - connect_start) * 1000

            if connect_elapsed < 50:
                client._reuse_count += 1
                client.debug_log(
                    f"✅ HTTP连接复用成功！耗时: {connect_elapsed:.2f}ms | 复用次数: {client._reuse_count}"
                )
            else:
                client._connection_count += 1
                client.debug_log(
                    f"🔄 HTTP新连接建立完成，耗时: {connect_elapsed:.2f}ms | 新建连接数: {client._connection_count}"
                )
                if connect_elapsed > 5000:
                    client.debug_log("⚠️ 警告：连接耗时超过5秒，可能存在网络问题")
            client.debug_log(f"HTTP版本: HTTP/{response.http_version}")

            # 更新最后请求时间
            client.last_request_time = time.time()

            if response.status_code != 200:
                error_text = await response.aread()
                err_msg = error_text.decode("utf-8", errors="ignore")[:200]
                client.debug_log(f"HTTP错误 {response.status_code}: {err_msg}")
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}: {err_msg}",
                    request=response.request,
                    response=response,
                )

            data_receive_start = time.time()
            first_chunk_received = False

            client.debug_log("开始接收流式响应...")

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                if not first_chunk_received:
                    first_chunk_time = (time.time() - data_receive_start) * 1000
                    counter["first_chunk"] = first_chunk_time
                    first_chunk_received = True
                    client.debug_log(f"=== 首包到达！耗时: {first_chunk_time:.2f}ms ===")

                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    client.debug_log("收到 [DONE] 信号")
                    break

                try:
                    data = json.loads(data_str)

                    # ===== DEBUG: 打印前 3 个 chunk 的完整内容 =====
                    if counter.get("debug_chunk_count", 0) < 3:
                        counter["debug_chunk_count"] = counter.get("debug_chunk_count", 0) + 1
                        raw_dump = json.dumps(data, ensure_ascii=False)[:500]
                        client.debug_log(f"[DEBUG-RESPONSE] chunk#{counter['debug_chunk_count']} 原始数据: {raw_dump}")

                    if "usage" in data and "choices" not in data:
                        yield ("", None, data["usage"])
                        continue

                    if "choices" in data and len(data["choices"]) > 0:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")

                        tool_calls = delta.get("tool_calls")

                        if not tool_calls:
                            function_call = delta.get("function_call")
                            if function_call:
                                tool_calls = [{"index": 0, "function": function_call}]

                        if not tool_calls:
                            tool_call = delta.get("tool_call")
                            if tool_call:
                                tool_calls = [{"index": 0, "function": tool_call}]

                        if content:
                            client.debug_log(f"已接收块 | 内容字符: {len(content)} | 内容预览: {content[:50]}")
                            yield (content, None, None)
                        if tool_calls:
                            client.debug_log(f"[DEBUG-RESPONSE] ✅ 收到工具调用! tool_calls={json.dumps(tool_calls, ensure_ascii=False)}")
                            yield ("", tool_calls, None)

                except json.JSONDecodeError as e:
                    client.debug_log(f"JSON解析失败: {str(e)}")

            data_receive_elapsed = (time.time() - data_receive_start) * 1000
            client.debug_log(f"数据接收完成 | 接收耗时: {data_receive_elapsed:.2f}ms")
            total_chunks = counter.get("chunks", 0)
            debug_chunks = counter.get("debug_chunk_count", 0)
            client.debug_log(f"[DEBUG-SUMMARY] 本轮流结束 | 总chunk数: {total_chunks} | debug_chunk_count: {debug_chunks}")


# 模块级单例
llm_streamer = LLMStreamer(llm_client)


async def stream_chat_request(
    messages: list,
    api_key: str,
    api_url: str,
    tools: List[dict] = None,
    model: str = "glm-5.1",
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
