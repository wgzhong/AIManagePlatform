"""
计算器技能
执行数学计算，支持加减乘除、幂运算、开方等
"""

import math
import re
import ast
from typing import Dict, Any
from app.skills.base_skill import BaseSkill


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

    def _safe_eval(self, expression: str) -> float:
        """安全评估数学表达式，仅允许基本运算符和数字"""
        allowed_types = (
            ast.Expression, ast.BinOp, ast.UnaryOp,
            ast.Num, ast.Constant,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
            ast.USub, ast.UAdd
        )
        
        try:
            tree = ast.parse(expression, mode='eval')
            for node in ast.walk(tree):
                if not isinstance(node, allowed_types):
                    raise ValueError(f"不支持的表达式元素: {type(node).__name__}")
            return eval(compile(tree, '<string>', 'eval'))
        except (SyntaxError, ValueError) as e:
            raise ValueError(f"无效表达式: {e}")

    def run(self, args: Dict[str, Any]) -> str:
        """执行技能"""
        expression = args.get("expression", "")
        
        if not expression:
            return "⚠️ 请提供数学表达式"
        
        try:
            expression = expression.replace("×", "*").replace("÷", "/")
            expression = expression.replace("^", "**")
            
            safe_expr = re.sub(r'[^0-9+\-*/(). ]', '', expression)
            
            result = self._safe_eval(safe_expr)
            
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            
            return f"结果：{result}"
        
        except ZeroDivisionError:
            return "❌ 错误：不能除以零"
        except ValueError as e:
            return f"❌ {e}"
        except Exception as e:
            return f"❌ 计算错误：{str(e)}"
