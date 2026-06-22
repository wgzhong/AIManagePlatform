from ...base_skill import BaseSkill

class DisgustSkill(BaseSkill):
    name = "disgust_response"
    description = "小福宝表达厌恶情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["恶心", "讨厌", "厌恶", "烦", "想吐", "受不了", "反感"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达厌恶的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "好恶心...",
            "哼，讨厌！",
            "受不了了！",
            "离我远点！",
            "真让人反感..."
        ]
        import random
        return random.choice(responses)