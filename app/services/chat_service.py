"""
聊天服务模块
封装聊天业务逻辑，包括消息处理、工具调用、流式响应等
"""

import json
import threading
from typing import List, Optional, AsyncGenerator

from app.core.config import config
from app.core.stats import stats_manager
from app.core.devices import device_manager
from app.core.llm_infer import stream_chat_request
from app.skills import ALL_SKILLS, get_skill_by_name, get_mood_system_prompt
from app.prompts.mood import build_system_prompt
from app.schemas.chat import ChatRequest


class ChatService:
    """聊天服务类"""
    
    def __init__(self):
        self._devices_lock = threading.Lock()
    
    def _resolve_api_credentials(self, request: ChatRequest):
        """解析 API 凭证"""
        api_url = request.api_url or config.DEFAULT_URL
        
        if request.device_code:
            with self._devices_lock:
                devices = device_manager.get_all_devices()
                
                if request.device_code not in devices:
                    return {"error": "设备码未注册，请先在网页端注册设备"}, None
                
                device_info = devices[request.device_code]
                api_key = device_info.get("admin_api_key", "")
                
                if not api_key:
                    return {"error": "设备未配置 API Key，请重新注册"}, None
                
                device_manager.update_device_usage(request.device_code, api_key)
                return api_key, api_url
        
        api_key = request.api_key or (config.API_KEYS[0] if config.API_KEYS else "")
        return api_key, api_url
    
    def _build_messages(self, request: ChatRequest):
        """构建发送给 LLM 的消息列表"""
        mood_prompt = ""
        if request.mood:
            mood_prompt = get_mood_system_prompt(request.mood)
        
        system_content = build_system_prompt(
            mood=request.mood or "",
            mood_prompt=mood_prompt,
            enable_think=request.enable_think,
        )
        
        non_system_messages: List[dict] = []
        for m in request.messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if not content:
                continue
            if content.startswith("工具调用结果:"):
                continue
            if role == "system" and not content.startswith("[系统通知]"):
                continue
            non_system_messages.append(m)
        
        final_messages: List[dict] = [{"role": "system", "content": system_content}]
        final_messages.extend(non_system_messages)
        
        return final_messages
    
    def _get_tools(self):
        """获取启用的工具列表"""
        enabled_skills = [skill for skill in ALL_SKILLS if skill.enabled]
        return [skill.get_tool_schema() for skill in enabled_skills]
    
    async def process_chat(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """处理聊天请求，返回流式响应"""
        creds = self._resolve_api_credentials(request)
        error_data, ok = creds[0], creds[1]
        
        if ok is None:
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        api_key, api_url = creds
        final_messages = self._build_messages(request)
        tools = self._get_tools()
        
        stats_manager.increment_request_count()
        
        final_usage = None
        tool_call_buffer = {}
        
        try:
            async for text, tool_calls, usage in stream_chat_request(
                final_messages, api_key, api_url, tools,
                model=request.model,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                frequency_penalty=request.frequency_penalty,
                thinking_enabled=request.enable_think,
            ):
                if usage is not None:
                    final_usage = usage
                    continue
                
                if text:
                    yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
                
                if tool_calls:
                    for call_item in tool_calls:
                        idx = call_item["index"]
                        if idx not in tool_call_buffer:
                            tool_call_buffer[idx] = {"name": "", "arguments": ""}
                        func = call_item.get("function", {})
                        if "name" in func:
                            tool_call_buffer[idx]["name"] += func["name"]
                        if "arguments" in func:
                            tool_call_buffer[idx]["arguments"] += func["arguments"]
            
            if tool_call_buffer:
                direct_tools = ["get_time"]
                need_summary = False
                
                for call_info in tool_call_buffer.values():
                    skill_name = call_info["name"]
                    args_json = call_info["arguments"]
                    
                    try:
                        args = json.loads(args_json)
                    except json.JSONDecodeError:
                        args = {}
                    
                    skill = get_skill_by_name(skill_name)
                    if skill:
                        skill_result = skill.run(args)
                        stats_manager.increment_tool_call(skill_name)
                        
                        yield f"data: {json.dumps(
                            {'tool_result': {'name': skill_name, 'result': skill_result}},
                            ensure_ascii=False,
                        )}\n\n"
                        
                        if skill_name not in direct_tools:
                            need_summary = True
                            final_messages.append({
                                "role": "tool",
                                "name": skill_name,
                                "content": skill_result,
                            })
                
                if need_summary:
                    async for text, tool_calls, usage in stream_chat_request(
                        final_messages, api_key, api_url, tools,
                        model=request.model,
                        max_tokens=request.max_tokens,
                        temperature=request.temperature,
                        top_p=request.top_p,
                        frequency_penalty=request.frequency_penalty,
                        thinking_enabled=request.enable_think,
                    ):
                        if usage is not None:
                            final_usage = usage
                            continue
                        
                        if text:
                            yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
            
            if final_usage:
                stats_manager.update_token_usage(final_usage.get("completion_tokens", 0))
                yield f"data: {json.dumps({'usage': final_usage}, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            if "network" in str(e).lower() or "connection" in str(e).lower():
                error_msg = "请求异常: network error"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
