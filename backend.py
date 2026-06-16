"""
MCP Client + FastAPI 后端
符合 Model Context Protocol 规范：
- 通过 STDIO transport 连接 MCP Server
- 发送 JSON-RPC 2.0 消息进行生命周期握手和工具调用
- 不依赖 MCP SDK ClientSession，直接用 subprocess 实现
- 支持 ESP32 设备码验证和 API Key 自动分配
"""

import asyncio
import json
import httpx
from fastapi import FastAPI, HTTPException, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import subprocess
import uuid
import secrets
from datetime import datetime
import threading

app = FastAPI()

API_KEYS_FILE = os.path.join(os.path.dirname(__file__), "api_keys.json")
DEVICES_FILE = os.path.join(os.path.dirname(__file__), "devices.json")
API_KEYS = ["your_api_key_1"]
DEFAULT_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MAX_USERS_PER_KEY = 50  # 每个 API Key 最多支持的用户数


def load_api_keys():
    """从文件加载 API Keys"""
    global API_KEYS
    if os.path.exists(API_KEYS_FILE):
        try:
            with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    API_KEYS = data
        except:
            pass


def save_api_keys():
    """保存 API Keys 到文件"""
    with open(API_KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(API_KEYS, f, ensure_ascii=False, indent=2)


def generate_api_key() -> str:
    """生成随机 API Key"""
    key = secrets.token_urlsafe(32)
    return key


def load_devices():
    """从文件加载设备信息"""
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_devices(devices: Dict):
    """保存设备信息到文件"""
    with open(DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)


def get_available_api_key() -> Optional[str]:
    """获取可用（有剩余配额）的 API Key"""
    devices = load_devices()
    
    # 统计每个 API Key 已分配的用户数
    key_usage = {}
    for device_code, info in devices.items():
        api_key = info.get("api_key", "")
        if api_key and api_key in API_KEYS:
            key_usage[api_key] = key_usage.get(api_key, 0) + 1
    
    # 找到一个还有余量的 API Key
    for key in API_KEYS:
        used = key_usage.get(key, 0)
        if used < MAX_USERS_PER_KEY:
            return key
    
    return None


def generate_device_code() -> str:
    """生成随机设备码（8位十六进制）"""
    return secrets.token_hex(4).upper()


# 初始化加载
load_api_keys()

_http_client = None
_mcp_process: Optional[subprocess.Popen] = None
_mcp_tools_cache: Optional[List[Dict]] = None
_devices_lock = threading.Lock()


async def get_http_client():
    global _http_client
    if _http_client is None:
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=50)
        timeout = httpx.Timeout(60.0, connect=10.0)
        _http_client = httpx.AsyncClient(http2=True, limits=limits, timeout=timeout)
    return _http_client


class ChatRequest(BaseModel):
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
    device_code: Optional[str] = None  # ESP32 设备码


# ============================================================
#  MCP Client: 直接用 subprocess + JSON-RPC 2.0
# ============================================================
def start_mcp_server() -> subprocess.Popen:
    """启动 MCP Server 进程（STDIO transport）"""
    global _mcp_process

    if _mcp_process is not None and _mcp_process.poll() is None:
        return _mcp_process

    server_path = os.path.join(os.path.dirname(__file__), "mcp_server.py")
    _mcp_process = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(__file__),
        text=True,
        bufsize=1,  # 行缓冲
    )
    return _mcp_process


def send_json_rpc(method: str, params: Dict = None, request_id: int = 1) -> Dict:
    """发送 JSON-RPC 2.0 请求并等待响应"""
    proc = start_mcp_server()

    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params or {},
    }

    # 发送请求（以换行符结束）
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()

    # 读取响应
    response_line = proc.stdout.readline()
    if not response_line:
        raise RuntimeError("MCP Server 未返回响应")

    response = json.loads(response_line.strip())

    if "error" in response:
        raise RuntimeError(f"MCP 错误: {response['error']}")

    return response.get("result", {})


def initialize_mcp() -> bool:
    """发送 initialize 请求进行生命周期握手"""
    result = send_json_rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "ai-chat-client", "version": "1.0.0"},
        },
        request_id=1,
    )

    # 发送 initialized notification
    proc = start_mcp_server()
    notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    proc.stdin.write(json.dumps(notification) + "\n")
    proc.stdin.flush()

    return True


def list_mcp_tools() -> List[Dict]:
    """调用 tools/list 获取工具列表"""
    global _mcp_tools_cache

    if _mcp_tools_cache is not None:
        return _mcp_tools_cache

    # 先确保初始化
    initialize_mcp()

    result = send_json_rpc("tools/list", {}, request_id=2)
    tools = result.get("tools", [])

    _mcp_tools_cache = [
        {
            "name": t.get("name"),
            "description": t.get("description", ""),
            "inputSchema": t.get("inputSchema", {}),
        }
        for t in tools
    ]

    return _mcp_tools_cache


def call_mcp_tool(name: str, arguments: Dict[str, Any]) -> str:
    """调用 tools/call 执行工具"""
    result = send_json_rpc("tools/call", {"name": name, "arguments": arguments}, request_id=3)

    content = result.get("content", [])
    texts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            texts.append(item.get("text", ""))
        elif hasattr(item, "text"):
            texts.append(item.text)

    return "\n".join(texts) if texts else "工具执行成功，但无返回内容"


# 快速工具调用匹配（跳过 LLM 决策，减少延迟）
def quick_tool_match(message: str) -> Optional[Dict]:
    """快速匹配常见工具调用场景，仅匹配明确的工具调用意图"""
    message = message.strip()
    
    # 时间查询：必须包含"几点"或"时间"，且不是简单问候
    time_keywords = ["几点", "时间", "时刻", "几点钟", "现在几点", "现在是几点"]
    if any(keyword in message for keyword in time_keywords):
        return {"tool": "get_time", "arguments": {}}
    
    # 数学计算：必须包含数字和运算符
    import re
    calc_pattern = r'([\d\.]+)\s*[+\-*/×÷]\s*([\d\.]+)'
    if re.search(calc_pattern, message):
        expr = re.search(calc_pattern, message).group(0).replace('×', '*').replace('÷', '/')
        return {"tool": "calculate", "arguments": {"expression": expr}}
    
    # 文件读取：必须包含"读取"或"查看"和路径
    if any(keyword in message for keyword in ["读取", "查看", "打开文件"]):
        path_match = re.search(r'([A-Za-z]:\\[^"\'\s]+)', message)
        if path_match:
            return {"tool": "read_file", "arguments": {"path": path_match.group(1)}}
    
    return None


def is_chitchat(message: str) -> bool:
    """判断是否是日常闲聊内容"""
    chitchat_keywords = [
        "你好", "您好", "嗨", "哈喽", "hello", "hi",
        "你是谁", "介绍一下你自己", "你叫什么",
        "再见", "拜拜", "goodbye",
        "谢谢", "感谢", "thanks",
        "聊天", "聊会天", "随便聊聊",
        "在吗", "在不在",
        "今天心情怎么样", "天气不错"
    ]
    message = message.strip().lower()
    return any(keyword in message for keyword in chitchat_keywords)


# ============================================================
#  System Prompt
# ============================================================
def build_tool_system_prompt(tools: List[Dict]) -> str:
    tools_json = json.dumps(tools, ensure_ascii=False, indent=2)

    return """你是一个可以调用外部工具的 AI 助手。

你可以调用以下工具（通过 MCP 协议提供）：

<TOOLS>
""" + tools_json + """
</TOOLS>

你的输出规则（必须严格遵守）：

1. 如果用户的问题可以通过工具更好地回答，你必须输出工具调用，格式是纯 JSON：
   {"tool": "工具名称", "arguments": {"参数名": "参数值"}}

   示例：
   - 用户问"现在几点？" → 输出：{"tool": "get_time", "arguments": {}}
   - 用户问"123 × 456 等于多少？" → 输出：{"tool": "calculate", "arguments": {"expression": "123*456"}}
   - 用户问"D:\\config.txt 里写了什么？" → 输出：{"tool": "read_file", "arguments": {"path": "D:\\config.txt"}}

2. 如果用户只是闲聊、问好、聊天内容与工具无关，你必须输出：
   {"tool": null}

3. 你每次最多只能调用一个工具。
4. 你的输出只能是上述两种 JSON 之一，不要包含任何其他字符。
"""


def parse_json_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """解析 LLM 输出的 JSON 工具调用"""
    if not text:
        return None
    text = text.strip()

    if text.startswith("{") and text.endswith("}"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    import re
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        try:
            return json.loads(text[first : last + 1])
        except json.JSONDecodeError:
            pass

    return None


def is_tool_call_decision(decision: Optional[Dict]) -> bool:
    """判断是否需要调用工具"""
    if not decision or not isinstance(decision, dict):
        return False
    tool_name = decision.get("tool")
    return isinstance(tool_name, str) and tool_name in ["get_time", "calculate", "read_file"]


# ============================================================
#  LLM 工具决策请求
# ============================================================
async def llm_tool_decision(request: ChatRequest, api_key: str, api_url: str) -> Optional[Dict]:
    """第 1 轮：让 LLM 决定是否需要调用工具"""
    client = await get_http_client()

    tools = list_mcp_tools()
    tool_prompt = build_tool_system_prompt(tools)

    recent_messages = list(request.messages[-5:]) if request.messages else []
    decision_messages = [{"role": "system", "content": tool_prompt}]
    for m in recent_messages:
        if m.get("role") != "system":
            decision_messages.append(m)

    payload = {
        "model": request.model,
        "messages": decision_messages,
        "stream": False,
        "max_tokens": 50,
        "temperature": 0.1,
        "top_p": 0.3,
        "thinking": {"type": "disabled"},  # 禁用思考模式，加快决策速度
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = await client.post(api_url, json=payload, headers=headers, timeout=30.0)
        if resp.status_code != 200:
            return None
        data = resp.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return parse_json_tool_call(reply)
    except Exception:
        return None


# ============================================================
#  /chat 端点（支持 ESP32 设备码验证）
# ============================================================
@app.post("/chat")
async def chat(request: ChatRequest):
    api_url = request.api_url or DEFAULT_URL
    
    # ESP32 设备码验证模式
    if request.device_code:
        with _devices_lock:
            devices = load_devices()
            
            if request.device_code not in devices:
                return StreamingResponse(
                    iter([f"data: {json.dumps({'error': '设备码未注册，请先在网页端注册设备'}, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]),
                    media_type="text/event-stream"
                )
            
            device_info = devices[request.device_code]
            api_key = device_info.get("admin_api_key", "")
            
            if not api_key or api_key not in API_KEYS:
                return StreamingResponse(
                    iter([f"data: {json.dumps({'error': '设备的管理员 API Key 无效，请检查'}, ensure_ascii=False)}\n\n", "data: [DONE]\n\n"]),
                    media_type="text/event-stream"
                )
            
            # 更新设备最后使用时间
            device_info["last_used"] = datetime.now().isoformat()
            device_info["usage_count"] = device_info.get("usage_count", 0) + 1
            devices[request.device_code] = device_info
            save_devices(devices)
    else:
        # 普通模式（网页端）
        api_key = request.api_key or API_KEYS[0]

    user_message = request.messages[-1]["content"] if request.messages else ""

    # 方案1：明确的工具调用，直接返回工具结果（最快，不经过 LLM）
    tool_decision = quick_tool_match(user_message)
    if tool_decision:
        tool_name = tool_decision["tool"]
        tool_arguments = tool_decision.get("arguments") or {}
        try:
            raw_result = call_mcp_tool(tool_name, tool_arguments)
        except Exception as e:
            raw_result = f"工具调用失败: {str(e)}"

        if tool_name == "get_time":
            response_text = f"现在是 {raw_result}"
        elif tool_name == "calculate":
            response_text = f"计算结果: {raw_result}"
        elif tool_name == "read_file":
            response_text = f"文件内容:\n{raw_result}"
        else:
            response_text = f"工具结果: {raw_result}"

        async def generate_tool_result():
            yield "data: " + json.dumps({"content": response_text}, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(generate_tool_result(), media_type="text/event-stream")

    # 方案2：正常对话，直接交给 LLM（跳过工具决策，减少延迟）
    original_user_system = None
    non_system_messages: List[dict] = []
    for m in request.messages:
        if m.get("role") == "system":
            original_user_system = m.get("content", "")
        else:
            # 过滤掉历史中的工具调用结果，避免上下文污染
            content = m.get("content", "")
            if content and not content.startswith("工具调用结果:"):
                non_system_messages.append(m)

    system_content = "你是一个聪明且友好的 AI 助手。请直接、简洁地回答用户的问题。"
    if request.enable_think:
        system_content = "你是一个聪明且有深度思考能力的 AI 助手。回答时可以展现你的思考过程。"
    if original_user_system:
        system_content += f" {original_user_system}"
    
    final_messages: List[dict] = [{"role": "system", "content": system_content}]
    final_messages.extend(non_system_messages)

    payload = {
        "model": request.model,
        "messages": final_messages,
        "stream": True,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "top_p": request.top_p,
        "top_k": request.top_k,
        "frequency_penalty": request.frequency_penalty,
        "n": 1,
    }
    if request.enable_think:
        payload["thinking"] = {"type": "enabled"}
    else:
        payload["thinking"] = {"type": "disabled"}
    
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    async def generate():
        client = await get_http_client()
        try:
            async with client.stream("POST", api_url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: [ERROR] {response.status_code} {error_text}\n\n"
                    return

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            yield "data: [DONE]\n\n"
                            break
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content") or delta.get("reasoning_content", "")
                                if content:
                                    yield "data: " + json.dumps({"content": content}, ensure_ascii=False) + "\n\n"
                        except json.JSONDecodeError:
                            pass
        except httpx.HTTPError as e:
            yield f"data: [ERROR] Connection error: {str(e)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================
#  页面路由
# ============================================================
@app.get("/devices")
async def devices_page():
    """硬件设备管理页面"""
    return FileResponse("static/devices.html")


# ============================================================
#  API Key 管理 API
# ============================================================
@app.post("/api/keys/generate")
async def generate_new_api_key():
    """生成新的随机 API Key"""
    new_key = generate_api_key()
    API_KEYS.append(new_key)
    save_api_keys()
    return {"key": new_key, "message": "API Key 生成成功"}


@app.get("/api/keys")
async def list_api_keys():
    """列出所有可用的 API Keys"""
    return {"keys": API_KEYS}


@app.delete("/api/keys/{key}")
async def delete_api_key(key: str):
    """删除指定的 API Key"""
    if key in API_KEYS:
        API_KEYS.remove(key)
        save_api_keys()
        return {"message": f"API Key 删除成功"}
    else:
        raise HTTPException(status_code=404, detail="API Key 不存在")


@app.post("/api/keys/validate")
async def validate_api_key(key: str = None):
    """验证 API Key 是否有效"""
    is_valid = key in API_KEYS if key else False
    return {"valid": is_valid}


# ============================================================
#  设备管理 API（ESP32 设备码）
# ============================================================
@app.post("/api/devices/register")
async def register_device(
    device_name: str = Form(default="Hardware Device"),
    admin_api_key: str = Form(default=None)
):
    """注册新设备，使用管理员的 API Key"""
    with _devices_lock:
        # 验证管理员 API Key
        if not admin_api_key or admin_api_key not in API_KEYS:
            return {
                "success": False,
                "error": "无效的管理员 API Key",
                "message": "请在主页输入有效的 API Key"
            }
        
        devices = load_devices()
        
        # 生成新设备码
        device_code = generate_device_code()
        
        # 确保设备码唯一
        while device_code in devices:
            device_code = generate_device_code()
        
        # 注册设备（使用管理员的 API Key）
        devices[device_code] = {
            "name": device_name,
            "admin_api_key": admin_api_key,  # 存储管理员的 API Key
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "usage_count": 0
        }
        
        save_devices(devices)
        
        return {
            "success": True,
            "device_code": device_code,
            "device_name": device_name,
            "message": f"设备注册成功！设备码：{device_code}"
        }


@app.get("/api/devices")
async def list_devices():
    """列出所有已注册的设备"""
    devices = load_devices()
    
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
        "api_keys_total": len(API_KEYS)
    }


@app.delete("/api/devices/{device_code}")
async def delete_device(device_code: str):
    """删除指定设备"""
    with _devices_lock:
        devices = load_devices()
        
        if device_code not in devices:
            raise HTTPException(status_code=404, detail="设备不存在")
        
        device_info = devices.pop(device_code)
        save_devices(devices)
        
        return {
            "success": True,
            "message": f"设备 {device_code} 已删除",
            "freed_api_key": device_info.get("api_key", "")[:20] + "..." if device_info.get("api_key") else ""
        }


@app.get("/api/devices/{device_code}")
async def get_device(device_code: str):
    """获取指定设备信息"""
    devices = load_devices()
    
    if device_code not in devices:
        raise HTTPException(status_code=404, detail="设备不存在")
    
    info = devices[device_code]
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
#  MCP 工具列表 API
# ============================================================
@app.get("/mcp/tools")
async def get_tools():
    """返回 MCP Server 提供的工具列表"""
    tools = list_mcp_tools()
    return {"tools": tools, "protocol": "MCP-2025-06-18", "transport": "stdio"}


# ============================================================
#  静态文件
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/chat")
async def chat_page():
    return FileResponse(os.path.join(STATIC_DIR, "chat.html"))


@app.get("/keys")
async def keys_page():
    return FileResponse(os.path.join(STATIC_DIR, "keys.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)