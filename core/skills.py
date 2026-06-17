"""
Skill 基础框架模块
提供 Skill 基类和注册机制
"""

from datetime import datetime
import math
from typing import List, Dict, Optional


class BaseSkill:
    """Skill 基类"""
    name: str = ""
    description: str = ""
    parameters: dict = {}

    def run(self, args: dict) -> str:
        """执行技能，返回结果字符串"""
        raise NotImplementedError

    def get_tool_schema(self) -> dict:
        """获取工具定义 Schema，用于 LLM 工具调用"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


class GetTimeSkill(BaseSkill):
    """获取当前系统时间 Skill"""
    name = "get_time"
    description = "获取当前服务器的年月日、星期、时分秒，用户询问现在几点、日期时调用"
    parameters = {
        "type": "object",
        "required": [],
        "properties": {}
    }

    def run(self, args: dict) -> str:
        now = datetime.now()
        week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        week = week_map[now.weekday()]
        time_str = now.strftime(f"%Y年%m月%d日 {week} %H:%M:%S")
        return f"当前系统时间：{time_str}"


class CalculateSkill(BaseSkill):
    """数学计算 Skill"""
    name = "calculate"
    description = "执行数学计算，支持加减乘除等基本运算"
    parameters = {
        "type": "object",
        "required": ["expression"],
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如：2+3*4"
            }
        }
    }

    def run(self, args: dict) -> str:
        expression = args.get("expression", "")
        try:
            result = eval(expression, {"__builtins__": None}, {"math": math})
            return f"计算结果：{result}"
        except Exception as e:
            return f"计算失败：{str(e)}"


class ReadFileSkill(BaseSkill):
    """读取文件内容 Skill"""
    name = "read_file"
    description = "读取指定路径的文件内容"
    parameters = {
        "type": "object",
        "required": ["path"],
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径，如：D:\\config.txt"
            }
        }
    }

    def run(self, args: dict) -> str:
        file_path = args.get("path", "")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return f"文件内容：\n{content}"
        except Exception as e:
            return f"读取失败：{str(e)}"


ALL_SKILLS = [GetTimeSkill(), CalculateSkill(), ReadFileSkill()]


def get_all_tool_definitions() -> List[dict]:
    """获取所有 Skill 的工具定义列表"""
    return [skill.get_tool_schema() for skill in ALL_SKILLS]


def get_skill_by_name(name: str) -> Optional[BaseSkill]:
    """根据名称获取 Skill 实例"""
    for skill in ALL_SKILLS:
        if skill.name == name:
            return skill
    return None