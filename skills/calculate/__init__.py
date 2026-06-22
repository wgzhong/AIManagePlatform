"""
计算器技能
执行数学计算，支持加减乘除、幂运算、开方等
"""

import math
import re
from typing import Dict, Any
from skills.base_skill import BaseSkill


class CalculateSkill(BaseSkill):
    """计算器技能"""

    name = "calculate"
    description = "执行数学计算，支持加减乘除、幂运算、开方等"
    icon = "🧮"
    category = "工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["计算", "算一下", "多少", "等于", "加减乘除"]

    parameters = {
        "type": "object",
        "required": [],
        "properties": {
            "expression": {"type": "string", "description": "数学表达式"}
        }
    }

    def run(self, args: Dict[str, Any]) -> str:
        """执行技能"""
        expression = args.get("expression", "")
        
        if not expression:
            return "⚠️ 请提供数学表达式"
        
        try:
            expression = expression.replace("×", "*").replace("÷", "/")
            expression = expression.replace("^", "**")
            
            safe_expr = re.sub(r'[^0-9+\-*/().%^&|~<>! ]', '', expression)
            
            result = eval(safe_expr)
            
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            
            return f"结果：{result}"
        
        except ZeroDivisionError:
            return "❌ 错误：不能除以零"
        except SyntaxError:
            return "❌ 错误：表达式格式不正确"
        except Exception as e:
            return f"❌ 计算错误：{str(e)}"
