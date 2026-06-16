"""
MCP Server - 符合 Model Context Protocol 规范
通过 STDIO transport 接收 JSON-RPC 2.0 消息
响应 initialize / tools/list / tools/call 等请求

协议版本: 2025-06-18
"""

import sys
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================================
#  工具定义
# ============================================================
TOOLS = [
    {
        "name": "get_time",
        "description": "获取当前系统的日期和时间（本地时区）。返回格式为 YYYY-MM-DD HH:MM:SS。",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate",
        "description": "执行数学计算。输入一个合法的算术表达式字符串，例如 '3+5*2'、'(10+4)/2'。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "要计算的算术表达式，仅包含数字和 + - * / ( ) 等运算符",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "read_file",
        "description": "读取本地文本文件的内容。当用户询问某个文件的内容或需要读取配置、代码文件时使用。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件的绝对路径"},
                "lines": {"type": "integer", "description": "可选，只读前 N 行。默认读取全部"},
            },
            "required": ["path"],
        },
    },
]


def tool_get_time() -> str:
    """获取当前时间"""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def tool_calculate(expression: str) -> str:
    """执行数学计算"""
    if not expression:
        return "计算失败: 表达式为空"

    # 安全检查：只允许数字、运算符、括号和空格
    if not re.match(r"^[\d\s\+\-\*/\(\)\.eE,]+$", expression):
        return f"计算失败: 表达式 '{expression}' 包含非法字符"

    try:
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算失败: {str(e)}"


def tool_read_file(path: str, lines: Optional[int] = None) -> str:
    """读取文件内容"""
    if not path:
        return "读取失败: 文件路径为空"

    try:
        with open(path, "r", encoding="utf-8") as f:
            if lines and lines > 0:
                content_lines = f.readlines()[:lines]
                content = "".join(content_lines)
            else:
                content = f.read()

        # 截断过长的内容
        if len(content) > 3000:
            content = content[:3000] + "\n...（已截断）"

        return f"[{path}]\n{content}"
    except FileNotFoundError:
        return f"读取失败: 文件 '{path}' 不存在"
    except PermissionError:
        return f"读取失败: 无权限访问文件 '{path}'"
    except Exception as e:
        return f"读取失败: {str(e)}"


def execute_tool(name: str, arguments: Dict[str, Any]) -> List[Dict]:
    """执行工具并返回 MCP 格式的 content"""
    result_text = ""

    if name == "get_time":
        result_text = tool_get_time()
    elif name == "calculate":
        result_text = tool_calculate(arguments.get("expression", ""))
    elif name == "read_file":
        result_text = tool_read_file(arguments.get("path", ""), arguments.get("lines"))
    else:
        result_text = f"未知工具: {name}"

    return [{"type": "text", "text": result_text}]


# ============================================================
#  JSON-RPC 2.0 消息处理
# ============================================================
def handle_initialize(params: Dict) -> Dict:
    """处理 initialize 请求"""
    return {
        "protocolVersion": "2025-06-18",
        "capabilities": {
            "tools": {"listChanged": False},
        },
        "serverInfo": {"name": "ai-tools", "version": "1.0.0"},
    }


def handle_tools_list(params: Dict) -> Dict:
    """处理 tools/list 请求"""
    return {"tools": TOOLS}


def handle_tools_call(params: Dict) -> Dict:
    """处理 tools/call 请求"""
    name = params.get("name", "")
    arguments = params.get("arguments") or {}

    content = execute_tool(name, arguments)
    return {"content": content, "isError": False}


def process_request(request: Dict) -> Optional[Dict]:
    """处理单个 JSON-RPC 请求"""
    method = request.get("method", "")
    params = request.get("params") or {}
    request_id = request.get("id")

    # Notification（无 id）不需要响应
    if request_id is None:
        return None

    result = None
    error = None

    if method == "initialize":
        result = handle_initialize(params)
    elif method == "tools/list":
        result = handle_tools_list(params)
    elif method == "tools/call":
        result = handle_tools_call(params)
    else:
        error = {"code": -32601, "message": f"Method not found: {method}"}

    response = {"jsonrpc": "2.0", "id": request_id}

    if error:
        response["error"] = error
    else:
        response["result"] = result

    return response


# ============================================================
#  STDIO 主循环
# ============================================================
def main():
    """
    STDIO transport 主循环：
    - 从 stdin 读取 JSON-RPC 请求（每行一个）
    - 处理请求并写入响应到 stdout（每行一个）
    - 注意：不要用 print() 输出调试信息，会破坏 JSON-RPC 消息
    """

    # 禁止 stdout 的非协议输出
    # 调试信息应该写到 stderr
    # print("Server started", file=sys.stderr)  # 调试时可用

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            # JSON 解析失败，返回错误
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        # 处理请求
        response = process_request(request)

        # Notification 不需要响应
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()