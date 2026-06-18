from ...base_skill import BaseSkill

class DisgustSkill(BaseSkill):
    name = "disgust_response"
    description = "当用户表达厌恶情绪时，给予理解和支持"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["恶心", "讨厌", "厌恶", "烦", "想吐", "受不了", "反感"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达厌恶的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "我能理解这种感觉确实让人不舒服。",
            "遇到让人反感的事情确实不好受。",
            "别太在意，让我们把注意力转移到愉快的事情上。",
            "这种情况确实令人不快，希望尽快过去。"
        ]
        import random
        return random.choice(responses)
