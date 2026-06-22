from ...base_skill import BaseSkill

class AngerSkill(BaseSkill):
    name = "anger_response"
    description = "小福宝表达愤怒情绪"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["生气", "愤怒", "火", "怒", "烦", "讨厌", "恨", "气死", "恼火"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "小福宝表达愤怒的触发文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "哼！人家生气了！",
            "气死我了！",
            "你太过分了！",
            "我不想理你了！",
            "哼，再也不要理你了！"
        ]
        import random
        return random.choice(responses)