from ...base_skill import BaseSkill

class FearSkill(BaseSkill):
    name = "fear_response"
    description = "小福宝表达恐惧情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["害怕", "恐惧", "怕", "担心", "焦虑", "紧张", "不安"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达恐惧的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "好可怕...",
            "我好害怕...",
            "躲起来...",
            "不要...",
            "瑟瑟发抖..."
        ]
        import random
        return random.choice(responses)