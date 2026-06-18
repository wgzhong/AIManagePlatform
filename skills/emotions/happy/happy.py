from ...base_skill import BaseSkill

class HappySkill(BaseSkill):
    name = "happy_response"
    description = "当用户表达快乐情绪时，给予热情回应"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["开心", "高兴", "快乐", "幸福", "满足", "美好", "爽"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达快乐的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "哇，真为你开心！希望这份快乐能一直延续！",
            "太棒了！听到你这么幸福我也很满足！",
            "快乐是最好的礼物，愿你每天都这么开心！",
            "看到你这么快乐，我的心情也变好了！",
            "愿这份美好的感觉永远伴随着你！"
        ]
        import random
        return random.choice(responses)
