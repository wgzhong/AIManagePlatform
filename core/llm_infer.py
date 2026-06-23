"""
LLM推理模块
负责处理与LLM服务的通信，包括HTTP客户端配置和流式请求处理
"""

import json
import os
import httpx
from httpx import AsyncHTTPTransport
import time
import asyncio
import logging
from typing import List, Dict, Optional, Any, Tuple

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None

logging_level = logging.DEBUG if os.environ.get("LLM_DEBUG", "false").lower() == "true" else logging.INFO

logging.basicConfig(
    level=logging_level,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("LLM")


class LLMInfer:
    """LLM推理客户端类"""
    
    LIMITS = httpx.Limits(
        max_connections=100, 
        max_keepalive_connections=20,
        keepalive_expiry=60.0  # 缩短到60秒，匹配服务器端可能的空闲超时
       
    )
    TIMEOUT = httpx.Timeout(60.0, connect=10.0)  # 缩短连接超时
    
    # SSL/TLS 会话缓存，复用 SSL 握手
    TRANSPORT = AsyncHTTPTransport(
        retries=0,
        http2=True,
        verify=False,
    )
    
    # 连接保活心跳间隔（秒）
    HEARTBEAT_INTERVAL = 30.0
    
    def __init__(self):
        """初始化LLM推理客户端"""
        self._client = None
        self._warmup_done = False
        self._debug_mode = os.environ.get("LLM_DEBUG", "false").lower() == "true"
        self._connection_count = 0
        self._reuse_count = 0
        self._heartbeat_task = None
        self._last_request_time = 0
        self._api_url = None
        self._api_key = None
    
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
                follow_redirects=False,
                verify=False,
                trust_env=False
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
    
    async def warmup(self, api_url: str, api_key: str = None):
        """
        预热HTTP连接，减少首次请求延迟
        使用真实请求建立并保持连接
        
        Args:
            api_url: API地址
            api_key: 可选的API Key，用于发送真实请求
        """
        if self._warmup_done:
            return
        
        self._api_url = api_url
        self._api_key = api_key
        
        client = self._get_client()
        
        # 预热策略：发送真实请求建立连接
        warmup_payload = {
            "model": "glm-5.1",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False
        }
        
        warmup_headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            warmup_headers["Authorization"] = f"Bearer {api_key}"
        
        try:
            start_time = time.time()
            # 发送真实请求建立连接
            response = await client.post(
                api_url, 
                json=warmup_payload, 
                headers=warmup_headers,
                timeout=15.0
            )
            elapsed = (time.time() - start_time) * 1000
            self._debug_log(f"连接预热完成，耗时: {elapsed:.2f}ms | 状态码: {response.status_code}")
            self._warmup_done = True
            self._last_request_time = time.time()
            
            # 启动心跳保活任务
            if api_key:
                self._start_heartbeat()
                
        except Exception as e:
            self._debug_log(f"预热失败: {str(e)[:80]}")
            # 即使失败也标记为已完成，避免反复预热
            self._warmup_done = True
    
    def _start_heartbeat(self):
        """启动心跳保活任务"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._debug_log(f"心跳保活任务已启动，间隔: {self.HEARTBEAT_INTERVAL}s")
    
    async def _heartbeat_loop(self):
        """心跳保活循环，定期发送请求保持连接活跃"""
        while True:
            try:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                # 只有在空闲超过心跳间隔时才发送心跳
                idle_time = time.time() - self._last_request_time
                if idle_time > self.HEARTBEAT_INTERVAL and self._api_url and self._api_key:
                    self._debug_log(f"发送心跳保活请求... (空闲: {idle_time:.0f}s)")
                    
                    client = self._get_client()
                    heartbeat_payload = {
                        "model": "glm-5.1",
                        "messages": [{"role": "user", "content": "heartbeat"}],
                        "max_tokens": 1,
                        "stream": False
                    }
                    heartbeat_headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._api_key}"
                    }
                    
                    start_time = time.time()
                    response = await client.post(
                        self._api_url,
                        json=heartbeat_payload,
                        headers=heartbeat_headers,
                        timeout=10.0
                    )
                    elapsed = (time.time() - start_time) * 1000
                    
                    if elapsed < 100:
                        self._debug_log(f"✅ 心跳成功，连接复用！耗时: {elapsed:.2f}ms")
                    else:
                        self._debug_log(f"心跳完成，耗时: {elapsed:.2f}ms | 状态: {response.status_code}")
                    
                    self._last_request_time = time.time()
                    
            except asyncio.CancelledError:
                self._debug_log("心跳任务已取消")
                break
            except Exception as e:
                self._debug_log(f"心跳失败: {str(e)[:50]}")
                # 继续尝试，不中断心跳循环
    
    def _truncate_messages(self, messages: List[dict], max_messages: int = 20) -> List[dict]:
        """
        智能截断历史消息，保留 system + 最近 N 条
        当消息数超过 max_messages 时触发
        """
        if len(messages) <= max_messages:
            return messages
        
        # 保留第一条 system 消息（如有）
        result = []
        for m in messages:
            if m.get("role") == "system":
                result.append(m)
                break
        
        # 取最后 max_messages - 1 条消息
        remaining = max_messages - len(result)
        result.extend(messages[-remaining:])
        
        self._debug_log(f"消息截断: {len(messages)} -> {len(result)} 条")
        return result
    
    def _estimate_messages_size(self, messages: List[dict]) -> int:
        """估算 messages 总体大小（字符数）"""
        return sum(len(str(m.get("content", ""))) for m in messages)
    
    def _fast_json_dumps(self, obj: Any) -> bytes:
        """快速 JSON 序列化，优先使用 orjson"""
        if HAS_ORJSON:
            return orjson.dumps(obj)
        return json.dumps(obj, ensure_ascii=False).encode("utf-8")
    
    def _build_payload_bytes(self, payload: dict) -> bytes:
        """将 payload 序列化为字节，orjson 比 stdlib 快 2-3 倍"""
        return self._fast_json_dumps(payload)
    
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
        
        # 智能截断过长历史，避免 payload 膨胀
        truncated_messages = self._truncate_messages(messages, max_messages=20)
        print(truncated_messages)
        msg_size = self._estimate_messages_size(truncated_messages)
        
        payload = {
            "model": model,
            "messages": truncated_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "frequency_penalty": frequency_penalty,
            "presence_penalty": presence_penalty,
            "thinking": {"type": "enabled" if thinking_enabled else "disabled"}
        }

        if tools:
            payload["tools"] = tools

        # 使用 orjson 预序列化 payload 为字节，避免 httpx 内部重复序列化
        serialize_start = time.time()
        payload_bytes = self._build_payload_bytes(payload)
        serialize_elapsed = (time.time() - serialize_start) * 1000
        payload_size_kb = len(payload_bytes) / 1024

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Content-Length": str(len(payload_bytes))
        }
        
        client = self._get_client()
        
        self._debug_log(f"===== 请求开始 =====")
        self._debug_log(f"消息数: {len(truncated_messages)}/{len(messages)} | 估算大小: {msg_size} 字符 | payload: {payload_size_kb:.1f}KB")
        self._debug_log(f"序列化耗时: {serialize_elapsed:.2f}ms | JSON库: {'orjson' if HAS_ORJSON else 'stdlib'}")
        self._debug_log(f"温度: {temperature} | top_p: {top_p}")
        self._debug_log(f"启用工具: {len(tools) if tools else 0} 个")
        self._log_connection_stats()
        
        connect_start = time.time()
        self._debug_log(f"开始建立HTTP连接...")
        self._debug_log(f"目标URL: {api_url}")
        
        async with client.stream(
            "POST", api_url, 
            content=payload_bytes,  # 直接传字节，跳过 httpx 内部 json 编码
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
            
            # 更新最后请求时间
            self._last_request_time = time.time()
            
            if response.status_code != 200:
                error_text = await response.aread()
                err_msg = error_text.decode("utf-8", errors="ignore")[:200]
                self._debug_log(f"HTTP错误 {response.status_code}: {err_msg}")
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
                    
        total_elapsed = (time.time() - request_start_time) * 1000
        self._debug_log(f"===== 请求完成 =====")
        self._debug_log(f"总耗时: {total_elapsed:.2f}ms | 数据块数: {chunk_count} | 输出字符: {total_content_chars}")
        if first_chunk_time:
            self._debug_log(f"首包延迟: {first_chunk_time:.2f}ms | 后续传输: {(total_elapsed - first_chunk_time):.2f}ms")

    async def close(self):
        """关闭HTTP客户端连接"""
        # 取消心跳任务
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
        
        if self._client:
            await self._client.aclose()
            self._client = None
            self._debug_log("HTTP客户端已关闭")


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