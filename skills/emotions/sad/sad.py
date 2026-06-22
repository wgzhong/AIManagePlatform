from ...base_skill import BaseSkill

class SadSkill(BaseSkill):
    name = "sad_response"
    description = "小福宝表达悲伤情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["伤心", "难过", "悲伤", "痛苦", "失落", "沮丧", "愁", "哭"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达悲伤的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "呜...好难过...",
            "眼泪止不住了...",
            "心好痛...",
            "没有人理解我...",
            "好想哭..."
        ]
        import random
        return random.choice(responses)