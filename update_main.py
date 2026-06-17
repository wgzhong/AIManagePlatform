import os

# 读取现有main.py内容
with open("main.py", "r", encoding="utf-8") as f:
    content = f.read()

# 替换导入语句
content = content.replace(
    "from core.mcp import mcp_manager",
    "from core.skills import get_all_tool_definitions, get_skill_by_name, ALL_SKILLS"
)
content = content.replace(
    "from core.llm_utils import llm_utils",
    "# Skill系统已包含工具匹配功能"
)

# 替换功能描述
content = content.replace(
    "description=\"AI 推理对话平台，支持 MCP 工具调用和设备管理\"",
    "description=\"AI 推理对话平台，支持 Skill 工具调用和设备管理\""
)

# 替换工具调用相关代码
content = content.replace(
    "tool_decision = llm_utils.quick_tool_match(user_message, request.enabled_tools)",
    "# Skill系统自动通过LLM工具调用"
)

# 写入更新后的内容
with open("main.py", "w", encoding="utf-8") as f:
    f.write(content)

print("main.py 更新完成")
