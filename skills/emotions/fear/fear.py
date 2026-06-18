from ...base_skill import BaseSkill

class FearSkill(BaseSkill):
    name = "fear_response"
    description = "当用户表达恐惧情绪时，给予安慰和鼓励"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["害怕", "恐惧", "怕", "担心", "焦虑", "紧张", "不安"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达恐惧的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "别怕，有我在呢，我们一起面对。",
            "恐惧是正常的情绪，你很勇敢地说出来了。",
            "深呼吸，一切都会好起来的，相信自己。",
            "我理解你的害怕，让我们一起想办法克服它。",
            "每个人都会有害怕的时候，你不是一个人。"
        ]
        import random
        return random.choice(responses)
