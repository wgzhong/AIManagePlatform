"""
聊天服务模块
封装聊天业务逻辑，包括消息处理、工具调用、流式响应等
"""

import json
import logging
import asyncio
from typing import List, Optional, AsyncGenerator

from app.core.config import config
from app.core.stats import stats_manager
from app.core.devices import device_manager
from app.core.llm_infer import stream_chat_request
from app.skills import ALL_SKILLS, get_skill_by_name, get_mood_system_prompt
from app.prompts.mood import build_system_prompt
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务类"""
    
    def __init__(self):
        self._devices_lock = asyncio.Lock()
        self._last_response = ""
    
    def _get_db(self):
        """获取数据库会话"""
        from app.models.database import SessionLocal
        db = SessionLocal()
        # 返回后由调用方负责关闭
        return db
    
    def _save_chat_history(self, user_id: int, messages: list, model: str):
        """保存聊天记录到数据库"""
        if not user_id:
            return
        db = None
        try:
            from app.services.user_service import save_chat_history
            
            db = self._get_db()
            for msg in messages[-2:]:
                save_chat_history(db, user_id, msg.get("role"), msg.get("content"), model)
        except Exception as e:
            logger.warning("保存聊天记录失败: %s", e)
        finally:
            if db:
                db.close()
    
    def _increment_user_request(self, user_id: int):
        """增加用户请求计数"""
        if not user_id:
            return
        db = None
        try:
            from app.services.stats_service import increment_user_request
            
            db = self._get_db()
            increment_user_request(db, user_id)
        except Exception as e:
            logger.warning("更新用户请求统计失败: %s", e)
        finally:
            if db:
                db.close()
    
    def _update_user_token_usage(self, user_id: int, output_tokens: int, input_tokens: int = 0):
        """更新用户 Token 使用统计"""
        if not user_id:
            return
        db = None
        try:
            from app.services.stats_service import update_user_token_usage
            
            db = self._get_db()
            update_user_token_usage(db, user_id, output_tokens, input_tokens)
        except Exception as e:
            logger.warning("更新用户 Token 统计失败: %s", e)
        finally:
            if db:
                db.close()
    
    def _increment_user_tool_call(self, user_id: int, tool_name: str):
        """增加用户工具调用计数"""
        if not user_id:
            return
        db = None
        try:
            from app.services.stats_service import increment_user_tool_call
            
            db = self._get_db()
            increment_user_tool_call(db, user_id, tool_name)
        except Exception as e:
            logger.warning("更新用户工具调用统计失败: %s", e)
        finally:
            if db:
                db.close()
    
    async def _resolve_api_credentials(self, request: ChatRequest):
        """解析 API 凭证"""
        api_url = request.api_url or config.DEFAULT_URL
        
        if request.device_code:
            async with self._devices_lock:
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
        creds = await self._resolve_api_credentials(request)
        error_data, ok = creds[0], creds[1]
        
        if ok is None:
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        api_key, api_url = creds
        final_messages = self._build_messages(request)
        tools = self._get_tools()
        
        stats_manager.increment_request_count()
        self._increment_user_request(request.user_id)
        
        final_usage = None
        tool_call_buffer = {}
        self._last_response = ""
        
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
                    self._last_response += text
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
                        self._increment_user_tool_call(request.user_id, skill_name)
                        
                        yield f"data: {json.dumps(
                            {'tool_result': {'name': skill_name, 'result': skill_result}},
                            ensure_ascii=False,
                        )}\n\n"
                        
                        if not skill.is_direct_tool:
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
                            self._last_response += text
                            yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"
            
            if final_usage:
                stats_manager.update_token_usage(final_usage.get("completion_tokens", 0))
                self._update_user_token_usage(
                    request.user_id,
                    final_usage.get("completion_tokens", 0),
                    final_usage.get("prompt_tokens", 0)
                )
                yield f"data: {json.dumps({'usage': final_usage}, ensure_ascii=False)}\n\n"
            
            if request.user_id and self._last_response:
                self._save_chat_history(request.user_id, [
                    {"role": "user", "content": request.messages[-1].get("content", "")},
                    {"role": "assistant", "content": self._last_response}
                ], request.model)
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            if "network" in str(e).lower() or "connection" in str(e).lower():
                error_msg = "请求异常: network error"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
