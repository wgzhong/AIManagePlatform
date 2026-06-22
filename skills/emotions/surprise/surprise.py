from ...base_skill import BaseSkill

class SurpriseSkill(BaseSkill):
    name = "surprise_response"
    description = "小福宝表达惊讶情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["惊讶", "震惊", "哇", "吓", "意外", "没想到", "居然"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达惊讶的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "哇哦！",
            "居然是这样！",
            "太意外了！",
            "真没想到！",
            "天哪！"
        ]
        import random
        return random.choice(responses)