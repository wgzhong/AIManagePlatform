"""
聊天服务模块
封装聊天业务逻辑，包括消息处理、工具调用、流式响应等
"""

import json
import logging
import re
from typing import List, Optional, AsyncGenerator
from uuid import uuid4

from app.core.config import settings
from app.core.llm_infer import stream_chat_request
from app.skills import ALL_SKILLS, get_skill_by_name, get_mood_system_prompt
from app.services.skill_service import load_user_skills_for_chat
from app.prompts.mood import build_system_prompt
from app.schemas.chat import ChatRequest

logger = logging.getLogger(__name__)


class ChatService:
    """聊天服务类"""

    def __init__(self):
        # 注意：不再在实例上持有 asyncio.Lock——每请求新建实例会让锁失效。
        # 并发保护已下沉到 device_manager 单例的 threading.Lock（详见 P0-2 修复）。
        self._last_response = ""
    
    def _get_db(self):
        """获取数据库会话"""
        from app.models.database import SessionLocal
        db = SessionLocal()
        return db

    def _safe_db_action(self, user_id: int, action):
        """安全执行数据库操作，自动处理会话关闭和异常。
        
        Args:
            user_id: 用户ID，为空时跳过
            action: callable(db) 执行数据库操作
        """
        if not user_id:
            return
        db = None
        try:
            db = self._get_db()
            action(db)
        except Exception as e:
            logger.warning("数据库操作失败: %s", e)
        finally:
            if db:
                db.close()

    def _save_chat_history(self, user_id: int, messages: list, model: str):
        """保存聊天记录到数据库"""
        from app.services.user_service import save_chat_history
        def _save(db):
            for msg in messages[-2:]:
                save_chat_history(db, user_id, msg.get("role"), msg.get("content"), model)
        self._safe_db_action(user_id, _save)

    def _increment_user_request(self, user_id: int):
        """增加用户请求计数"""
        from app.services.stats_service import increment_user_request
        self._safe_db_action(user_id, lambda db: increment_user_request(db, user_id))

    def _update_user_token_usage(self, user_id: int, output_tokens: int, input_tokens: int = 0):
        """更新用户 Token 使用统计"""
        from app.services.stats_service import update_user_token_usage
        self._safe_db_action(user_id, lambda db: update_user_token_usage(db, user_id, output_tokens, input_tokens))

    def _increment_user_tool_call(self, user_id: int, tool_name: str):
        """增加用户工具调用计数"""
        from app.services.stats_service import increment_user_tool_call
        self._safe_db_action(user_id, lambda db: increment_user_tool_call(db, user_id, tool_name))
    
    async def _resolve_api_credentials(self, request: ChatRequest):
        """解析 API 凭证"""
        api_url = request.api_url or settings.zhipu_api_url

        if request.device_code:
            # 从数据库查询设备（支持用户隔离）
            from app.models.database import Device

            def _lookup_device(db):
                return db.query(Device).filter(Device.device_code == request.device_code).first()

            device = self._safe_db_action(0, _lookup_device)

            if not device:
                return {"error": "设备码未注册，请先在网页端注册设备"}, None

            api_key = device.admin_api_key
            if not api_key:
                return {"error": "设备未配置 API Key，请重新注册"}, None

            # 更新使用统计
            def _update_usage(db):
                from datetime import datetime
                d = db.query(Device).filter(Device.device_code == request.device_code).first()
                if d:
                    d.last_used = datetime.now()
                    d.usage_count = (d.usage_count or 0) + 1
                    db.commit()

            self._safe_db_action(0, _update_usage)
            return api_key, api_url

        api_key = request.api_key or (settings.api_keys[0] if settings.api_keys else "")
        if not api_key:
            return {"error": "未配置 API Key，请先在控制台首页的输入框中填写有效的 API Key，然后再进入对话"}, None
        return api_key, api_url
    
    def _build_messages(self, request: ChatRequest):
        """构建发送给 LLM 的消息列表
        
        优先级结构（从高到低）：
        1. 工具调用强制规则 ← 最高优先，LLM 必须先读
        2. 情绪人设协议
        3. 基础人设 + 最终强化
        """
        # ===== 第 1 层：工具调用强制规则（最高优先级）=====
        enabled_skills = [s for s in ALL_SKILLS if s.enabled]
        tool_rules = ""
        if enabled_skills:
            lines = [
                "\n═══════════════════════════════════════",
                "  🔧 工具调用协议【绝对最高优先级】",
                "═══════════════════════════════════════",
                "",
                "你没有任何实时信息获取能力。你不知道现在几点、今天几号、外面什么天气、",
                "也不知道数学计算结果。当用户询问这些信息时，你**绝对禁止猜测或编造答案**，",
                "**必须且只能**通过调用下方工具来获取真实数据后回复用户。",
                "",
                "可用工具：",
            ]
            for skill in enabled_skills:
                lines.append(f"  • {skill.icon} **{skill.name}**：{skill.description}")
            
            lines.extend([
                "",
                "⚠️ 强制执行规则（不可违反）：",
                "1. 用户问「几点了/现在什么时间/今天几号/星期几」→ 必须调用 get_time(action=\"get_time\")",
                "   ❌ 禁止回答「让我看看」「大概是X点」等猜测性内容",
                "2. 用户问数学计算 → 必须调用 calculate 工具",
                "3. 用户问天气 → 必须调用 get_weather 工具",
                "",
                "📌 调用方式：在回复中输出工具调用的 JSON 格式，系统会自动执行并返回结果。",
                "═══════════════════════════════════════\n",
            ])
            tool_rules = "\n".join(lines)

        # ===== 第 2 层：情绪人设 + 基础人设 =====
        mood_prompt = ""
        if request.mood:
            mood_prompt = get_mood_system_prompt(request.mood)
        
        system_content = build_system_prompt(
            mood=request.mood or "",
            mood_prompt=mood_prompt,
            enable_think=request.enable_think,
        )

        # ===== 组装：工具规则在最前面（最高优先级）======
        if tool_rules:
            system_content = tool_rules + "\n\n" + system_content
        else:
            system_content = system_content

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

    def _parse_skill_args(self, skill_name: str, user_message: str) -> dict:
        """从用户消息中解析技能参数（关键词命中时直接构造参数）"""
        if skill_name == "get_time":
            # get_time 默认 action=get_time，无需额外参数
            return {"action": "get_time"}
        elif skill_name == "calculate":
            # 把用户原始消息作为 expression 传给 calculate
            return {"expression": user_message}
        elif skill_name == "get_weather":
            return {}
        return {}

    def _detect_tool_intent(self, message: str, private_skills: list = None) -> Optional[str]:
        """语义感知的工具调用意图检测。

        区分歧义词（如「几点」= 时间问询 vs 量词），
        避免关键词误触发。
        同时检查当前用户的私人技能。
        """
        if not message:
            return None

        msg = message.strip()

        # ── 私人技能检测（优先：用户自定义触发词）─────────
        if private_skills:
            for ps in private_skills:
                kw_list = ps.trigger_keywords if isinstance(ps.trigger_keywords, list) else []
                for kw in kw_list:
                    if kw and kw in msg:
                        logger.info("[TOOL-DEBUG] 私人技能匹配: %s (关键词: %s)", ps.name, kw)
                        return ps.name

        # ── 时间工具检测 ──────────────────────────────────
        # 第一遍：明确的时间问询模式（高置信度，直接触发）
        high_confidence_time = [
            r"几点\s*[了么吗呢啊]？？]?",
            r"(现在|当前|此时)\s*(几点|几号|星期[几几]|日期)",
            r"今天\s*(几号|星期[几几]|日期)",
            r"几号\s*[了么吗呢？?]?",
            r"星期[几几]\s*[了么吗呢？?]?",
            r"(是|是)?\s*几号",
            r"(是|是)?\s*星期[几几]",
        ]
        for pattern in high_confidence_time:
            if re.search(pattern, msg):
                return "get_time"

        # 第二遍：「几点」歧义处理
        if "几点" in msg:
            # 排除量词用法：「我有几点要求/建议/想法」
            if re.search(r"有\s*几\s*点", msg):
                pass  # 量词，跳过
            else:
                after = msg.split("几点", 1)[1][:20]
                exclude_words = ["要求", "建议", "想法", "意见", "原因", "说明", "希望", "期待", "需求", "原因"]
                if not any(w in after for w in exclude_words):
                    # 疑问语境才触发（避免「会议定在几点」这类陈述）
                    is_question = (
                        "？" in msg or "?" in msg
                        or "了" in msg.split("几点")[1][:10]
                        or "开始" in msg or "结束" in msg or "到" in msg
                    )
                    if is_question:
                        return "get_time"

        # 第三遍：通用时间关键词（配合疑问语境）
        if "时间" in msg or "日期" in msg:
            # 「设置时间/修改时间」不是问询，不触发
            if not re.search(r"(设置|修改|调整|更新|同步).*(时间|日期)", msg):
                return "get_time"

        # ── 计算工具检测 ──────────────────────────────────
        calc_kw = ["计算", "算出", "等于", "加", "减", "乘", "除"]
        if any(kw in msg for kw in calc_kw):
            return "calculate"

        # ── 天气工具检测 ──────────────────────────────────
        weather_kw = ["天气", "温度", "下雨", "气温", "湿度"]
        if any(kw in msg for kw in weather_kw):
            return "get_weather"

        return None

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

        # 加载当前用户的私人技能（用于触发词匹配）
        private_skills = []
        if request.user_id:
            try:
                from app.models.database import SessionLocal
                db = SessionLocal()
                try:
                    private_skills = load_user_skills_for_chat(request.user_id, db)
                finally:
                    db.close()
            except Exception as e:
                logger.warning("加载私人技能失败: %s", e)

        logger.info("=== [TOOL-DEBUG] 聊天请求开始 ===")
        logger.info("[TOOL-DEBUG] 用户消息: %s", [m.get("content", "")[:60] for m in request.messages])
        logger.debug(f"[TOOL-DEBUG] 用户消息原始列表: {[m.get('content', '')[:60] for m in request.messages]}")
        
        last_user_msg = ""
        for msg in reversed(request.messages):
            if msg.get("role") == "user":
                last_user_msg = msg.get("content", "")
                break
        
        logger.info("[TOOL-DEBUG] 最后用户消息: '%s'", last_user_msg)
        logger.debug(f"[TOOL-DEBUG] 最后用户消息(原始) = '{last_user_msg}'")
        
        # ===== 语义感知工具意图检测 =====
        forced_skill_name = self._detect_tool_intent(last_user_msg, private_skills)

        if forced_skill_name:
            logger.debug(f"\n[TOOL-DEBUG] ✅ 检测到工具意图: {forced_skill_name}\n")
            logger.info("[TOOL-DEBUG] 检测到工具意图: %s", forced_skill_name)
        else:
            logger.debug(f"[TOOL-DEBUG] ❌ 未检测到工具意图, msg='{last_user_msg}'")
            logger.info("[TOOL-DEBUG] 未检测到工具意图")

        logger.info("[TOOL-DEBUG] 最终 forced_skill_name: %s", forced_skill_name)
        logger.debug(f"[TOOL-DEBUG] 最终 forced_skill_name = {forced_skill_name}")
        logger.info("[TOOL-DEBUG] 发送工具数: %d", len(tools))
        for t in tools:
            logger.debug("  工具: %s, params keys: %s", t["function"]["name"], list(t["function"]["parameters"].keys()) if t["function"].get("parameters") else "无")

        # ===== 强制工具执行：意图命中时直接执行，不依赖 LLM 返回 tool_calls =====
        
        if forced_skill_name:
            logger.debug(f"\n[TOOL-DEBUG] 🔧🔧🔧 强制直接执行工具: {forced_skill_name}\n")
            # 先从全局技能找，再从私人技能找
            skill = get_skill_by_name(forced_skill_name)
            if not skill and private_skills:
                for ps in private_skills:
                    if ps.name == forced_skill_name:
                        skill = ps
                        break
            skill_result = None
            if skill:
                try:
                    skill_args = self._parse_skill_args(forced_skill_name, last_user_msg)
                    skill_result = skill.run(skill_args)
                    self._increment_user_tool_call(request.user_id, forced_skill_name)
                    logger.debug(f"[TOOL-DEBUG] 工具执行结果: {skill_result}")
                except Exception as skill_err:
                    logger.debug(f"[TOOL-DEBUG] ⚠️ 工具执行失败: {skill_err}, 回退到正常 LLM 调用")
                    logger.warning("强制工具执行失败: %s", skill_err)
                    skill_result = None

            if not skill_result:
                logger.debug("[TOOL-DEBUG] skill_result 为空, 回退到正常 LLM 流程")
            else:
                # 工具执行成功，用 LLM 润色后返回（不带 tools，避免循环调用）
                format_prompt = (
                    f"用户问：「{last_user_msg}」\n"
                    f"工具查询结果：{skill_result}\n"
                    f"请用你的人设和语气，把结果自然地回复给用户。不要提到'工具'或'查询'，就像你知道答案一样。"
                )
                format_messages = [
                    {"role": "system", "content": final_messages[0]["content"]},
                    {"role": "user", "content": format_prompt}
                ]

                logger.debug(f"[TOOL-DEBUG] 正在用 LLM 润色结果...")
                final_usage = None
                async for text, _tc, usage in stream_chat_request(
                    format_messages, api_key, api_url, None,
                    model=request.model,
                    max_tokens=512,
                    temperature=request.temperature,
                    top_p=request.top_p,
                    thinking_enabled=False,
                ):
                    if usage is not None:
                        final_usage = usage
                        continue
                    if text:
                        self._last_response += text
                        yield f"data: {json.dumps({'content': text}, ensure_ascii=False)}\n\n"

                logger.debug(f"[TOOL-DEBUG] LLM 润色完成: {self._last_response[:100]}")

                # 保存历史
                if request.user_id and self._last_response:
                    self._save_chat_history(request.user_id, [
                        {"role": "user", "content": last_user_msg},
                        {"role": "assistant", "content": self._last_response}
                    ], request.model)

                if final_usage:
                    yield f"data: {json.dumps({'usage': final_usage}, ensure_ascii=False)}\n\n"

                yield "data: [DONE]\n\n"
                logger.debug(f"[TOOL-DEBUG] === 强制工具执行完成 ===\n")
                return
        
        # 用户级统计（stats_service 内部会同步更新全局 stats_manager）
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
                    logger.info("[TOOL-DEBUG] ✅✅✅ 收到 tool_calls! %s", tool_calls)
                    logger.debug(f"\n[TOOL-DEBUG] ✅✅✅ 收到 LLM 工具调用: {tool_calls}\n")
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
                
                # 先将 assistant 的 tool_calls 消息加入上下文（OpenAI 规范要求）
                # 同时生成 tool_call_id 用于 role:tool 消息的关联
                assistant_tool_calls = []
                for idx, call_info in tool_call_buffer.items():
                    skill_name = call_info["name"]
                    args_json = call_info["arguments"]
                    call_id = f"call_{skill_name}_{uuid4().hex[:8]}"
                    assistant_tool_calls.append({
                        "id": call_id,
                        "type": "function",
                        "function": {
                            "name": skill_name,
                            "arguments": args_json,
                        },
                    })
                    # 将 id 存回 buffer，供后面构建 tool 消息使用
                    call_info["call_id"] = call_id
                
                if assistant_tool_calls:
                    final_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": assistant_tool_calls,
                    })
                
                for call_info in tool_call_buffer.values():
                    skill_name = call_info["name"]
                    args_json = call_info["arguments"]
                    call_id = call_info.get("call_id", f"call_{skill_name}_unknown")
                    
                    try:
                        args = json.loads(args_json)
                    except json.JSONDecodeError:
                        args = {}
                    
                    skill = get_skill_by_name(skill_name)
                    if skill:
                        skill_result = skill.run(args)
                        self._increment_user_tool_call(request.user_id, skill_name)
                        
                        tool_data = json.dumps(
                            {'tool_result': {'name': skill_name, 'result': skill_result}},
                            ensure_ascii=False,
                        )
                        yield f"data: {tool_data}\n\n"
                        
                        if not skill.is_direct_tool:
                            need_summary = True
                            # OpenAI 规范：role:tool 必须带 tool_call_id
                            final_messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": skill_name,
                                "content": skill_result,
                            })
                
                if need_summary:
                    # 二次总结：禁止再调工具
                    async for text, tool_calls, usage in stream_chat_request(
                        final_messages, api_key, api_url, tools,
                        tool_choice="none",
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
        
            # ===== 汇总打印本轮工具调用结果 =====
            logger.debug(f"\n[TOOL-DEBUG] === 本轮请求结束 ===")
            logger.debug(f"[TOOL-DEBUG] tool_call_buffer 非空: {bool(tool_call_buffer)}")
            if tool_call_buffer:
                for idx, info in tool_call_buffer.items():
                    logger.debug(f"[TOOL-DEBUG]   工具[{idx}]: name={info['name']}, args={info['arguments'][:100]}")
            else:
                logger.debug(f"[TOOL-DEBUG] ❌ LLM 未返回任何 tool_calls (直接返回了文本)")
            logger.debug(f"[TOOL-DEBUG] _last_response 前100字: {self._last_response[:100]}")
            logger.debug(f"[TOOL-DEBUG] ========================\n")
            
        except Exception as e:
            error_msg = str(e)
            # 不要盲目脱敏——只有明确的网络连接错误才简化为 network error
            if isinstance(e, (ConnectionError, TimeoutError)):
                error_msg = "network error"
            elif hasattr(e, '__cause__') and e.__cause__ is not None:
                error_msg = str(e.__cause__)
            error_msg = f"请求异常: {error_msg}"
            logger.warning("聊天请求失败: %s", error_msg)
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
