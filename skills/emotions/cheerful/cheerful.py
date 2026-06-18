from ...base_skill import BaseSkill

class CheerfulSkill(BaseSkill):
    name = "cheerful_response"
    description = "当用户表达开心情绪时，给予积极回应和祝福"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["开心", "高兴", "快乐", "幸福", "兴奋", "喜悦", "愉快", "乐", "笑", "太棒"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达开心的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "听到你这么开心，我也很快乐！",
            "太棒了！希望这份好心情一直伴随着你！",
            "开心是会传染的，谢谢你把快乐分享给我！",
            "看到你这么高兴，我也跟着开心起来了！",
            "愿你每天都像今天这样开心！"
        ]
        import random
        return random.choice(responses)
