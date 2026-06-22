from ...base_skill import BaseSkill

class HappySkill(BaseSkill):
    name = "happy_response"
    description = "小福宝表达快乐情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["开心", "高兴", "快乐", "幸福", "满足", "美好", "爽"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达快乐的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "哇！我好开心呀！",
            "哈哈哈哈，太开心啦！",
            "今天真是美好的一天！",
            "耶！太棒了！",
            "我好幸福呀！"
        ]
        import random
        return random.choice(responses)