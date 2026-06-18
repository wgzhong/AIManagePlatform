import math
from ...base_skill import BaseSkill

class CalculateSkill(BaseSkill):
    name = "calculate"
    description = "执行数学计算，支持加减乘除等基本运算"
    category = "计算工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["计算", "等于", "+", "-", "*", "/"]
    parameters = {"type": "object", "required": ["expression"], "properties": {"expression": {"type": "string", "description": "数学表达式"}}}
    
    def run(self, args):
        try:
            return f"计算结果：{eval(args.get('expression', ''), {'__builtins__': None}, {'math': math})}"
        except Exception as e:
            return f"计算失败：{str(e)}"
