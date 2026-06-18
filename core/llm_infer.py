"""
LLM推理模块
负责处理与LLM服务的通信，包括HTTP客户端配置和流式请求处理
"""

import json
import httpx
import time
import asyncio
from typing import List, Dict, Optional, Any, Tuple


class LLMInfer:
    """LLM推理客户端类"""
    
    LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=50)
    TIMEOUT = httpx.Timeout(60.0, connect=15.0)
    
    def __init__(self):
        """初始化LLM推理客户端"""
        self._client = None
        self._warmup_done = False
    
    def _get_client(self):
        """获取HTTP客户端，复用连接以提高性能"""
        if self._client is None:
            start_time = time.time()
            self._client = httpx.AsyncClient(
                http2=True, 
                limits=self.LIMITS, 
                timeout=self.TIMEOUT,
                headers={"User-Agent": "AIManagePlatform/1.0"},
                follow_redirects=True,
                verify=False,
                trust_env=True,
                http1=False
            )
            _client_init_time = (time.time() - start_time) * 1000
            print(f"[LLM] HTTP客户端初始化耗时: {_client_init_time:.2f}ms")
        return self._client
    
    async def warmup(self, api_url: str):
        """
        预热HTTP连接，减少首次请求延迟
        
        Args:
            api_url: API地址
        """
        if self._warmup_done:
            return
        
        client = self._get_client()
        try:
            start_time = time.time()
            async with client.stream("POST", api_url, json={}, headers={}, timeout=10.0):
                pass
            elapsed = (time.time() - start_time) * 1000
            print(f"[LLM] 连接预热完成，耗时: {elapsed:.2f}ms")
            self._warmup_done = True
        except Exception:
            pass
    
    async def stream_chat_request(
        self,
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
        max_retries: int = 2
    ) -> Tuple[str, Optional[List[dict]], Optional[dict]]:
        """
        发送流式请求，使用简洁的 aiter_lines() 处理 SSE 流
        返回异步生成器：(content_text, tool_calls_chunk, usage)
        
        Args:
            messages: 消息列表
            api_key: API密钥
            api_url: API地址
            tools: 工具定义列表
            model: 模型名称
            max_tokens: 最大生成token数
            temperature: 温度参数
            top_p: top_p参数
            frequency_penalty: 频率惩罚
            presence_penalty: 存在惩罚
            thinking_enabled: 是否启用思考模式
            max_retries: 最大重试次数
        
        Returns:
            三元组: (content_text, tool_calls_chunk, usage)
        """
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
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
        
        client = self._get_client()
        
        for attempt in range(max_retries + 1):
            try:
                async with client.stream(
                    "POST", api_url, 
                    json=payload, 
                    headers=headers,
                    timeout=self.TIMEOUT
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        err_msg = error_text.decode("utf-8", errors="ignore")[:200]
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 + attempt * 0.3)
                            continue
                        else:
                            raise httpx.HTTPStatusError(
                                f"HTTP {response.status_code}: {err_msg}",
                                request=response.request,
                                response=response
                            )
                    
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            return
                        
                        try:
                            data = json.loads(data_str)
                            
                            if "usage" in data and "choices" not in data:
                                yield ("", None, data["usage"])
                                continue
                            
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                tool_calls = delta.get("tool_calls")
                                
                                if content:
                                    yield (content, None, None)
                                if tool_calls:
                                    yield ("", tool_calls, None)
                                    
                        except json.JSONDecodeError:
                            pass
                    return
                    
            except httpx.HTTPError as e:
                if attempt < max_retries:
                    await asyncio.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    raise
            except asyncio.TimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2.0 + attempt)
                    continue
                else:
                    raise
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    raise

    async def close(self):
        """关闭HTTP客户端连接"""
        if self._client:
            await self._client.aclose()
            self._client = None


llm_infer = LLMInfer()


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
    max_retries: int = 2
) -> Tuple[str, Optional[List[dict]], Optional[dict]]:
    """
    向后兼容的流式请求接口
    调用全局实例的方法
    """
    async for result in llm_infer.stream_chat_request(
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
        max_retries=max_retries
    ):
        yield result
