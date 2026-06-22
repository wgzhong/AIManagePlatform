from ...base_skill import BaseSkill

class CheerfulSkill(BaseSkill):
    name = "cheerful_response"
    description = "小福宝表达愉快情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["开心", "高兴", "快乐", "幸福", "兴奋", "喜悦", "愉快", "乐", "笑", "太棒"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达愉快的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "嘻嘻嘻~",
            "好高兴呀！",
            "开心到起飞！",
            "心情美美哒！",
            "今天也是元气满满的一天！"
        ]
        import random
        return random.choice(responses)