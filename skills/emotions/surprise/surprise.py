from ...base_skill import BaseSkill

class SurpriseSkill(BaseSkill):
    name = "surprise_response"
    description = "当用户表达惊讶情绪时，给予有趣的回应"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["惊讶", "震惊", "哇", "吓", "意外", "没想到", "居然"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达惊讶的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "哇哦，确实很让人惊讶呢！",
            "真没想到会这样，太有趣了！",
            "哈哈，是不是吓了你一跳？",
            "哇，这真是个惊喜！",
            "世界真奇妙，总有意想不到的事情！"
        ]
        import random
        return random.choice(responses)
