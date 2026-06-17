"""
LLM推理模块
负责处理与LLM服务的通信，包括HTTP客户端配置和流式请求处理
"""

import json
import httpx
from typing import List, Dict, Optional, Any, Tuple


LIMITS = httpx.Limits(max_connections=50, max_keepalive_connections=20)
TIMEOUT = httpx.Timeout(30.0)


async def stream_chat_request(
    messages: list, 
    api_key: str, 
    api_url: str, 
    tools: List[dict] = None,
    model: str = "glm-5.1",
    max_completion_tokens: int = 1024,
    temperature: float = 1.0,
    top_p: float = 0.95,
    frequency_penalty: float = 0,
    presence_penalty: float = 0,
    thinking_enabled: bool = False
) -> Tuple[str, Optional[List[dict]], Optional[dict]]:
    """
    发送流式请求，手动解析 SSE 流
    返回迭代器：(content_text, tool_calls_chunk, usage)
    """
    payload = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_completion_tokens,
        "temperature": temperature,
        "top_p": top_p,
        "stream": True,
        "stop": None,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
        "extra_body": {
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
        }
    }

    if tools:
        payload["tools"] = tools

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(http2=True, limits=LIMITS, timeout=TIMEOUT) as client:
        async with client.stream("POST", api_url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            buffer = ""
            byte_iter = resp.aiter_bytes(1024)
            while True:
                try:
                    chunk = await byte_iter.__anext__()
                except StopAsyncIteration:
                    break
                buffer += chunk.decode("utf-8")
                while "\n\n" in buffer:
                    part, buffer = buffer.split("\n\n", 1)
                    lines = part.splitlines()
                    for line in lines:
                        if not line.startswith("data: "):
                            continue
                        data_raw = line[6:].strip()
                        if data_raw == "[DONE]":
                            continue
                        try:
                            data = json.loads(data_raw)
                        except json.JSONDecodeError:
                            continue
                        if "usage" in data and "choices" not in data:
                            yield ("", None, data["usage"])
                            continue
                        choices = data.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        text = delta.get("content", "")
                        tool_calls = delta.get("tool_calls")
                        yield (text, tool_calls, None)