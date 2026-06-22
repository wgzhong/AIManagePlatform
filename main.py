"""
AI Manage Platform - 主入口文件
调用core模块中的功能，提供FastAPI服务
"""

import asyncio
import json
import httpx
import logging
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os

logging_level = logging.DEBUG if os.environ.get("LLM_DEBUG", "false").lower() == "true" else logging.INFO

logging.basicConfig(
    level=logging_level,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger("APP")
import sys
import uuid
import secrets
from datetime import datetime
import threading

# 导入核心模块
from core.config import config
from core.stats import stats_manager
from core.chat_history import chat_history_manager
from core.api_keys import api_key_manager
from core.devices import device_manager
from core.reminder_manager import reminder_manager
from skills import get_all_tool_definitions, get_skill_by_name, ALL_SKILLS, get_all_skill_configs, get_mood_system_prompt, invalidate_tool_cache
from core.llm_infer import stream_chat_request, llm_infer

# 创建 FastAPI 应用实例
app = FastAPI(
    title="AI Manage Platform",
    description="AI 推理对话平台，支持 Skill 工具调用和设备管理",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
_http_client = None
_devices_lock = threading.Lock()


@app.on_event("startup")
async def startup_event():
    """应用启动时执行的初始化操作"""
    logger.info("正在预热LLM连接...")
    # 使用配置中的第一个 API Key 进行预热
    warmup_key = config.API_KEYS[0] if config.API_KEYS else None
    await llm_infer.warmup(config.DEFAULT_URL, warmup_key)

    logger.info("正在启动提醒管理器...")
    reminder_manager.start()


async def get_http_client():
    """获取 HTTP 客户端（单例）"""
    global _http_client
    if _http_client is None:
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        timeout = httpx.Timeout(60.0, connect=10.0)
        _http_client = httpx.AsyncClient(http2=True, limits=limits, timeout=timeout)
    return _http_client


class ChatRequest(BaseModel):
    """聊天请求模型"""
    messages: List[dict]
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    model: str = "glm-5.1"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.7
    top_k: int = 50
    frequency_penalty: float = 0.5
    enable_think: bool = False
    device_code: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    mood: Optional[str] = None  # 当前情绪状态


# ============================================================
#  /chat 端点（支持 ESP32 设备码验证和 Skill 工具调用）
# ============================================================
@app.post("/chat")
async def chat(request: ChatRequest):
    """处理聊天请求，支持 Skill 工具调用"""
    api_url = request.api_url or config.DEFAULT_URL
    
    # ESP32 设备码验证模式
    if request.device_code:
        with _devices_lock:
            devices = device_manager.get_all_devices()
            
            if request.device_code not in devices:
                return StreamingResponse(
                    iter([f"data: {json.dumps({'error': '设备码未注册，请先在网页端注册设备'}, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]),
                    media_type="text/event-stream"
                )
            
            device_info = devices[request.device_code]
            api_key = device_info.get("admin_api_key", "")
            
            if not api_key:
                return StreamingResponse(
                    iter([f"data: {json.dumps({'error': '设备未配置 API Key，请重新注册'}, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]),
                    media_type="text/event-stream"
                )
            
            device_manager.update_device_usage(request.device_code, api_key)
    else:
        api_key = request.api_key or config.API_KEYS[0]

    user_message = request.messages[-1]["content"] if request.messages else ""
    
    stats_manager.increment_request_count()

    enabled_skills = [skill for skill in ALL_SKILLS if skill.enabled]
    tools = [skill.get_tool_schema() for skill in enabled_skills]

    # 过滤消息：保留非 system 消息，以及带特殊标记的 system 消息（如[系统通知]）
    non_system_messages: List[dict] = []
    for m in request.messages:
        role = m.get("role", "")
        content = m.get("content", "")
        if not content:
            continue
        if content.startswith("工具调用结果:"):
            continue
        if role == "system" and not content.startswith("[系统通知]"):
            # 普通 system 消息由后端统一管理，过滤掉
            continue
        non_system_messages.append(m)

    # 基础人设固定在后端
    system_content = "你是小福宝，一个可爱的AI助手。主要服务日常对话，也能支持视频或者图片识别。"
    if request.enable_think:
        system_content = "你是一个聪明且有深度思考能力的 AI 助手。回答时可以展现你的思考过程。"
    
    # 追加情绪相关描述（由对应 skill 提供）
    if request.mood:
        mood_prompt = get_mood_system_prompt(request.mood)
        logger.info(f"使用心情: {request.mood}, 提示长度: {len(mood_prompt)}, 提示前30字: {mood_prompt[:30]}")
        # 把心情提示放在最前面，强化覆盖效果
        system_content = f"{mood_prompt}\n\n{system_content}"
        # 在末尾追加强制提醒
        system_content += f"\n\n【重要提醒】你当前必须严格按照上面的【{request.mood}】状态回复每一条消息，忽略之前所有对话中的语气风格。任何回复都必须以{request.mood}的语气表达，不要使用其他情绪。"
    
    final_messages: List[dict] = [{"role": "system", "content": system_content}]
    final_messages.extend(non_system_messages)

    async def generate():
        final_usage = None
        tool_call_buffer = {}

        try:
            async for text, tool_calls, usage in stream_chat_request(final_messages, api_key, api_url, tools):
                if usage is not None:
                    final_usage = usage
                    continue
                
                if text:
                    yield "data: " + json.dumps({"content": text}, ensure_ascii=False) + "\n\n"
                
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
                        
                        yield "data: " + json.dumps({"tool_result": {"name": skill_name, "result": skill_result}}, ensure_ascii=False) + "\n\n"
                        
                        final_messages.append({
                            "role": "tool",
                            "name": skill_name,
                            "content": skill_result
                        })

                async for text, tool_calls, usage in stream_chat_request(final_messages, api_key, api_url, tools):
                    if usage is not None:
                        final_usage = usage
                        continue
                    
                    if text:
                        yield "data: " + json.dumps({"content": text}, ensure_ascii=False) + "\n\n"

            if final_usage:
                stats_manager.update_token_usage(final_usage.get("completion_tokens", 0))
                yield "data: " + json.dumps({"usage": final_usage}, ensure_ascii=False) + "\n\n"
            
            yield "data: [DONE]\n\n"
        
        except Exception as e:
            error_msg = f"请求异常: {str(e)}"
            if "network" in str(e).lower() or "connection" in str(e).lower():
                error_msg = "请求异常: network error"
            yield f"data: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================
#  API Key 管理 API
# ============================================================
@app.post("/api/keys/generate")
async def generate_new_api_key():
    """生成新的随机 API Key"""
    new_key = api_key_manager.generate_key()
    api_key_manager.add_key(new_key)
    return {"key": new_key, "message": "API Key 生成成功"}


@app.get("/api/keys")
async def list_api_keys():
    """列出所有可用的 API Keys"""
    return {"keys": api_key_manager.load_keys()}


@app.delete("/api/keys/{key}")
async def delete_api_key(key: str):
    """删除指定的 API Key"""
    if api_key_manager.remove_key(key):
        return {"message": f"API Key 删除成功"}
    else:
        raise HTTPException(status_code=404, detail="API Key 不存在")


@app.post("/api/keys/validate")
async def validate_api_key(key: str = None):
    """验证 API Key 是否有效"""
    is_valid = api_key_manager.validate_key(key) if key else False
    return {"valid": is_valid}


# ============================================================
#  设备管理 API（ESP32 设备码）
# ============================================================
@app.post("/api/devices/register")
async def register_device(
    device_name: str = Form(default="Hardware Device"),
    admin_api_key: str = Form(default=None)
):
    """注册新设备，使用用户提供的 API Key"""
    if not admin_api_key or len(admin_api_key) < 10:
        return {
            "success": False,
            "error": "请提供有效的 API Key",
            "message": "请在首页输入您的 API Key 后再注册设备"
        }
    
    device_code = secrets.token_hex(4).upper()
    
    devices = device_manager.get_all_devices()
    while device_code in devices:
        device_code = secrets.token_hex(4).upper()
    
    devices[device_code] = {
        "name": device_name,
        "admin_api_key": admin_api_key,
        "created_at": datetime.now().isoformat(),
        "last_used": None,
        "usage_count": 0
    }
    
    with open(config.DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "device_code": device_code,
        "device_name": device_name,
        "message": f"设备注册成功！设备码：{device_code}"
    }


@app.get("/api/devices")
async def list_devices():
    """列出所有已注册的设备"""
    devices = device_manager.get_all_devices()
    
    device_list = []
    for device_code, info in devices.items():
        admin_key = info.get("admin_api_key", "")
        device_list.append({
            "device_code": device_code,
            "name": info.get("name", ""),
            "admin_api_key_short": admin_key[:20] + "..." if admin_key else "",
            "created_at": info.get("created_at", ""),
            "last_used": info.get("last_used", ""),
            "usage_count": info.get("usage_count", 0)
        })
    
    return {
        "devices": device_list,
        "total": len(device_list),
        "api_keys_total": len(api_key_manager.load_keys())
    }


@app.delete("/api/devices/{device_code}")
async def delete_device(device_code: str):
    """删除指定设备"""
    devices = device_manager.get_all_devices()
    
    if device_code not in devices:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    device_info = devices.pop(device_code)
    
    with open(config.DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)
    
    return {
        "success": True,
        "message": f"Device {device_code} deleted",
        "freed_api_key": device_info.get("admin_api_key", "")[:20] + "..." if device_info.get("admin_api_key") else ""
    }


@app.get("/api/devices/{device_code}")
async def get_device(device_code: str):
    """获取指定设备信息"""
    info = device_manager.get_device(device_code)
    
    if info is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    admin_key = info.get("admin_api_key", "")
    return {
        "device_code": device_code,
        "name": info.get("name", ""),
        "admin_api_key": admin_key,
        "admin_api_key_short": admin_key[:20] + "..." if admin_key else "",
        "created_at": info.get("created_at", ""),
        "last_used": info.get("last_used", ""),
        "usage_count": info.get("usage_count", 0)
    }


# ============================================================
#  系统统计 API
# ============================================================
@app.get("/api/stats")
async def get_stats():
    """获取系统统计数据"""
    stats = stats_manager.load_stats()
    devices = device_manager.get_all_devices()
    
    online_count = 0
    now = datetime.now()
    for info in devices.values():
        last_used = info.get("last_used")
        if last_used:
            last_time = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
            if (now - last_time).total_seconds() < 300:
                online_count += 1
    
    uptime = now - config.SYSTEM_START_TIME
    uptime_str = f"{uptime.days}天 {uptime.seconds//3600}时 {(uptime.seconds//60)%60}分"
    
    daily_records = stats.get("daily_records", [])
    today_count = stats.get("daily_requests", 0)
    yesterday_count = 0
    if len(daily_records) >= 2:
        yesterday_count = daily_records[-2].get("count", 0)
    
    growth_rate = 0
    if yesterday_count > 0:
        growth_rate = ((today_count - yesterday_count) / yesterday_count * 100)
    
    return {
        "daily_requests": today_count,
        "total_requests": stats.get("total_requests", 0),
        "growth_rate": round(growth_rate, 1),
        "online_devices": online_count,
        "total_devices": len(devices),
        "today_output_tokens": stats.get("today_output_tokens", 0),
        "total_output_tokens": stats.get("total_output_tokens", 0),
        "tool_calls": stats.get("tool_calls", {}),
        "daily_records": daily_records,
        "uptime": uptime_str,
        "version": "1.0.0",
        "skill_version": "2025-06-18"
    }


# ============================================================
#  对话历史 API
# ============================================================
@app.get("/api/chat/history")
async def get_chat_history():
    """获取对话历史"""
    history = chat_history_manager.load_history()
    return {"history": history}


class ChatHistoryRequest(BaseModel):
    history: List[dict]


@app.post("/api/chat/history")
async def api_save_chat_history(request: ChatHistoryRequest):
    """保存对话历史"""
    chat_history_manager.save_history(request.history)
    return {"success": True}


@app.delete("/api/chat/history")
async def clear_chat_history():
    """清空对话历史"""
    chat_history_manager.save_history([])
    return {"success": True}


# ============================================================
#  健康检查 API
# ============================================================
@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    try:
        client = await get_http_client()
        response = await client.head(config.DEFAULT_URL, timeout=5)
        latency = response.elapsed.total_seconds() * 1000
        
        if response.status_code == 200:
            status = "online"
            status_color = "green"
        elif 400 <= response.status_code < 500:
            status = "rate_limited"
            status_color = "orange"
        else:
            status = "error"
            status_color = "red"
    except Exception:
        status = "offline"
        status_color = "red"
        latency = -1
    
    return {
        "status": status,
        "status_color": status_color,
        "latency": round(latency, 1) if latency >= 0 else None,
        "timestamp": datetime.now().isoformat()
    }


# ============================================================
#  Skill 工具列表 API
# ============================================================
@app.get("/api/skills")
async def get_skills():
    """返回所有注册的 Skill 工具列表（包含高级配置）"""
    configs = get_all_skill_configs()
    return {"skills": configs, "protocol": "Skill-2025-06-18"}

@app.get("/api/skills/config")
async def get_skills_config():
    """返回所有技能的完整配置信息"""
    configs = get_all_skill_configs()
    return {"configs": configs}

@app.post("/api/skills/{skill_name}/config")
async def update_skill_config(skill_name: str, config: Dict[str, Any]):
    """更新指定技能的配置"""
    skill = get_skill_by_name(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if "enabled" in config:
        skill.enabled = config["enabled"]
    if "auto_trigger" in config:
        skill.auto_trigger = config["auto_trigger"]
    if "trigger_keywords" in config:
        skill.trigger_keywords = config["trigger_keywords"]

    return {"success": True, "message": f"技能 {skill_name} 配置已更新"}


@app.get("/api/skills/{skill_name}/system-prompt")
async def get_skill_system_prompt(skill_name: str):
    """获取指定技能的 system prompt 内容"""
    skill = get_skill_by_name(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    return {
        "skill_name": skill_name,
        "system_prompt": skill.get_system_prompt(),
        "mood_system_prompt": skill.get_mood_system_prompt(skill_name.split("_")[0] if "_" in skill_name else ""),
        "has_md_files": {
            "system_prompt": skill._skill_path is not None and os.path.isfile(skill._skill_path),
            "mood_prompt": skill._skill_path is not None and os.path.isfile(skill._skill_path),
        }
    }


class SystemPromptRequest(BaseModel):
    """System prompt 更新请求模型"""
    content: str
    prompt_type: str = "system_prompt"  # "system_prompt" 或 "mood_prompt"


@app.post("/api/skills/{skill_name}/system-prompt")
async def save_skill_system_prompt(skill_name: str, request: SystemPromptRequest):
    """保存指定技能的 system prompt 到 md 文件"""
    skill = get_skill_by_name(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    if request.prompt_type == "system_prompt":
        success = skill.save_system_prompt(request.content)
        message = "System prompt"
    elif request.prompt_type == "mood_prompt":
        success = skill.save_mood_prompt(request.content)
        message = "Mood prompt"
    else:
        raise HTTPException(status_code=400, detail="无效的 prompt_type")

    if success:
        # 清除 tool cache 使更改立即生效
        invalidate_tool_cache()
        return {"success": True, "message": f"{message} 已保存到 md 文件"}
    else:
        raise HTTPException(status_code=500, detail="保存失败，可能是权限问题")


@app.get("/api/skills/{skill_name}/file-path")
async def get_skill_file_path(skill_name: str):
    """获取指定技能的资源目录路径"""
    skill = get_skill_by_name(skill_name)
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")

    skill_path = skill.get_skill_path()
    return {
        "skill_name": skill_name,
        "skill_path": skill_path,
        "skill_dir": skill.get_skill_dir(),
        "md_file_path": skill_path if skill_path and os.path.isfile(skill_path) else None,
    }


# ============================================================
#  心情提示 API
# ============================================================
@app.get("/api/mood-prompt/{mood}")
async def get_mood_prompt_api(mood: str):
    """获取指定心情的 prompt 内容"""
    from skills import get_mood_system_prompt
    prompt = get_mood_system_prompt(mood)
    return {
        "mood": mood,
        "prompt": prompt
    }


# ============================================================
#  提醒管理 API
# ============================================================

@app.get("/api/reminders")
async def get_reminders(status: Optional[str] = None):
    """获取所有提醒"""
    reminders = reminder_manager.get_all_reminders(status)
    return {"reminders": reminders}


@app.get("/api/reminders/{reminder_id}")
async def get_reminder(reminder_id: str):
    """获取单个提醒"""
    reminder = reminder_manager.get_reminder(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="提醒不存在")
    return reminder


class SetReminderRequest(BaseModel):
    """设置提醒请求模型"""
    message: str
    minutes: Optional[int] = None
    hour: Optional[int] = None
    minute: Optional[int] = None


@app.post("/api/reminders")
async def set_reminder(request: SetReminderRequest):
    """设置提醒"""
    if request.minutes is not None:
        reminder_id = reminder_manager.set_reminder_in_minutes(request.message, request.minutes)
    elif request.hour is not None and request.minute is not None:
        reminder_id = reminder_manager.set_reminder_at_time(request.message, request.hour, request.minute)
    else:
        raise HTTPException(status_code=400, detail="请提供 minutes 或 hour+minute")

    return {"success": True, "reminder_id": reminder_id}


@app.delete("/api/reminders/{reminder_id}")
async def cancel_reminder(reminder_id: str):
    """取消提醒"""
    if reminder_manager.cancel_reminder(reminder_id):
        return {"success": True, "message": f"提醒 {reminder_id} 已取消"}
    else:
        raise HTTPException(status_code=404, detail="提醒不存在")


@app.get("/api/notifications")
async def notifications():
    """SSE 实时通知推送"""
    async def event_generator():
        async for message in reminder_manager.subscribe():
            yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================
#  静态文件服务
# ============================================================
STATIC_DIR = os.path.join(config.BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    """首页"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/chat")
async def chat_page():
    """聊天页面"""
    return FileResponse(os.path.join(STATIC_DIR, "chat.html"))


@app.get("/devices")
async def devices_page():
    """设备管理页面"""
    return FileResponse(os.path.join(STATIC_DIR, "devices.html"))


@app.get("/skills")
async def skills_page():
    """Skills 配置页面"""
    return FileResponse(os.path.join(STATIC_DIR, "skills.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)