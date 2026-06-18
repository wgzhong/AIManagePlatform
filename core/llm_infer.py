"""
LLM推理模块
负责处理与LLM服务的通信，包括HTTP客户端配置和流式请求处理
"""

import json
import httpx
from httpx import AsyncHTTPTransport
import time
import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("LLM")


class LLMInfer:
    """LLM推理客户端类"""
    
    LIMITS = httpx.Limits(
        max_connections=100, 
        max_keepalive_connections=50,
        keepalive_expiry=300.0
    )
    TIMEOUT = httpx.Timeout(60.0, connect=30.0)
    
    # SSL/TLS 会话缓存，复用 SSL 握手
    TRANSPORT = AsyncHTTPTransport(
        retries=0,
        http2=True
    )
    
    def __init__(self):
        """初始化LLM推理客户端"""
        self._client = None
        self._warmup_done = False
        self._debug_mode = True
        self._connection_count = 0
        self._reuse_count = 0
    
    def _debug_log(self, msg: str):
        """调试日志输出（使用 logging 替代 print）"""
        if self._debug_mode:
            logger.debug(msg)
    
    def _get_client(self):
        """获取HTTP客户端，复用连接以提高性能"""
        if self._client is None:
            start_time = time.time()
            self._client = httpx.AsyncClient(
                transport=self.TRANSPORT,
                limits=self.LIMITS, 
                timeout=self.TIMEOUT,
                headers={"User-Agent": "AIManagePlatform/1.0"},
                follow_redirects=True,
                verify=False,
                trust_env=True
            )
            _client_init_time = (time.time() - start_time) * 1000
            self._debug_log(f"HTTP客户端初始化耗时: {_client_init_time:.2f}ms")
            self._debug_log(f"HTTP/2 模式: 已启用 | SSL会话缓存: 已启用")
        else:
            self._debug_log(f"HTTP客户端复用成功，已存在实例")
        return self._client
    
    def _log_connection_stats(self):
        """记录连接统计信息"""
        try:
            if self._client and hasattr(self._client, '_transport'):
                transport = getattr(self._client, '_transport', None)
                if transport and hasattr(transport, '_pool'):
                    pool = getattr(transport, '_pool', None)
                    if pool:
                        active = getattr(pool, '_connections_active', 'N/A')
                        idle = getattr(pool, '_connections_idle', 'N/A')
                        self._debug_log(f"连接池状态 - 活跃连接: {active}, 空闲连接: {idle}")
        except Exception as e:
            self._debug_log(f"连接池状态获取失败: {type(e).__name__}")
    
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
            self._debug_log(f"连接预热完成，耗时: {elapsed:.2f}ms")
            self._warmup_done = True
        except Exception as e:
            self._debug_log(f"预热失败（可能正常）: {str(e)[:50]}")
    
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
        """
        request_start_time = time.time()
        total_content_chars = 0
        chunk_count = 0
        
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
        
        self._debug_log(f"===== 请求开始 =====")
        self._debug_log(f"消息数: {len(messages)} | 模型: {model} | max_tokens: {max_tokens}")
        self._debug_log(f"temperature: {temperature} | top_p: {top_p}")
        self._debug_log(f"启用工具: {len(tools) if tools else 0} 个")
        self._log_connection_stats()
        
        for attempt in range(max_retries + 1):
            attempt_start_time = time.time()
            self._debug_log(f"第 {attempt+1}/{max_retries+1} 次尝试")
            
            try:
                connect_start = time.time()
                self._debug_log(f"开始建立HTTP连接...")
                self._debug_log(f"目标URL: {api_url}")
                
                async with client.stream(
                    "POST", api_url, 
                    json=payload, 
                    headers=headers,
                ) as response:
                    connect_elapsed = (time.time() - connect_start) * 1000
                    
                    if connect_elapsed < 50:
                        self._reuse_count += 1
                        self._debug_log(f"✅ HTTP连接复用成功！耗时: {connect_elapsed:.2f}ms | 复用次数: {self._reuse_count}")
                    else:
                        self._connection_count += 1
                        self._debug_log(f"🔄 HTTP新连接建立完成，耗时: {connect_elapsed:.2f}ms | 新建连接数: {self._connection_count}")
                        if connect_elapsed > 5000:
                            self._debug_log(f"⚠️ 警告：连接耗时超过5秒，可能存在网络问题")
                    self._debug_log(f"HTTP版本: HTTP/{response.http_version}")
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        err_msg = error_text.decode("utf-8", errors="ignore")[:200]
                        self._debug_log(f"HTTP错误 {response.status_code}: {err_msg}")
                        if attempt < max_retries:
                            self._debug_log(f"等待 {(0.5 + attempt * 0.3):.1f}s 后重试...")
                            await asyncio.sleep(0.5 + attempt * 0.3)
                            continue
                        else:
                            raise httpx.HTTPStatusError(
                                f"HTTP {response.status_code}: {err_msg}",
                                request=response.request,
                                response=response
                            )
                    
                    data_receive_start = time.time()
                    first_chunk_received = False
                    first_chunk_time = None
                    
                    self._debug_log(f"开始接收流式响应...")
                    
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        
                        chunk_count += 1
                        if not first_chunk_received:
                            first_chunk_time = (time.time() - data_receive_start) * 1000
                            first_chunk_received = True
                            self._debug_log(f"=== 首包到达！耗时: {first_chunk_time:.2f}ms ===")
                        
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            self._debug_log(f"收到 [DONE] 信号")
                            break
                        
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
                                    total_content_chars += len(content)
                                    if chunk_count % 5 == 0:
                                        self._debug_log(f"已接收 {chunk_count} 块 | 累计字符: {total_content_chars}")
                                    yield (content, None, None)
                                if tool_calls:
                                    self._debug_log(f"收到工具调用: {tool_calls}")
                                    yield ("", tool_calls, None)
                                    
                        except json.JSONDecodeError as e:
                            self._debug_log(f"JSON解析失败: {str(e)}")
                    
                    data_receive_elapsed = (time.time() - data_receive_start) * 1000
                    self._debug_log(f"数据接收完成 | 数据块数: {chunk_count} | 接收耗时: {data_receive_elapsed:.2f}ms")
                    return
                    
            except httpx.HTTPError as e:
                attempt_elapsed = (time.time() - attempt_start_time) * 1000
                self._debug_log(f"HTTP错误: {str(e)[:50]} | 尝试耗时: {attempt_elapsed:.2f}ms")
                if attempt < max_retries:
                    await asyncio.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    raise
            except asyncio.TimeoutError:
                attempt_elapsed = (time.time() - attempt_start_time) * 1000
                self._debug_log(f"请求超时 | 尝试耗时: {attempt_elapsed:.2f}ms")
                if attempt < max_retries:
                    await asyncio.sleep(2.0 + attempt)
                    continue
                else:
                    raise
            except Exception as e:
                attempt_elapsed = (time.time() - attempt_start_time) * 1000
                self._debug_log(f"未知错误: {type(e).__name__}: {str(e)[:50]} | 尝试耗时: {attempt_elapsed:.2f}ms")
                if attempt < max_retries:
                    await asyncio.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    total_elapsed = (time.time() - request_start_time) * 1000
                    self._debug_log(f"===== 请求失败 =====")
                    self._debug_log(f"总耗时: {total_elapsed:.2f}ms | 失败原因: {type(e).__name__}")
                    raise
        
        total_elapsed = (time.time() - request_start_time) * 1000
        self._debug_log(f"===== 请求完成 =====")
        self._debug_log(f"总耗时: {total_elapsed:.2f}ms | 数据块数: {chunk_count} | 输出字符: {total_content_chars}")
        if first_chunk_time:
            self._debug_log(f"首包延迟: {first_chunk_time:.2f}ms | 后续传输: {(total_elapsed - first_chunk_time):.2f}ms")

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