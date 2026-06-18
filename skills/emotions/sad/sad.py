from ...base_skill import BaseSkill

class SadSkill(BaseSkill):
    name = "sad_response"
    description = "当用户表达悲伤情绪时，给予安慰和支持"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["伤心", "难过", "悲伤", "痛苦", "失落", "沮丧", "愁", "哭"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达悲伤的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "抱抱你，难过的时候哭出来会好一些。",
            "我理解你的感受，有什么想说的都可以跟我说。",
            "每个人都有难过的时候，这很正常，给自己一些时间。",
            "不要独自承受，我在这里陪着你。",
            "一切都会过去的，明天会更好。"
        ]
        import random
        return random.choice(responses)
