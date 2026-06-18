from ...base_skill import BaseSkill

class AngerSkill(BaseSkill):
    name = "anger_response"
    description = "当用户表达愤怒情绪时，提供安抚和理解的回应"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["生气", "愤怒", "火", "怒", "烦", "讨厌", "恨", "气死", "恼火"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达愤怒的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "我理解你的感受，遇到这种情况确实会让人很生气。",
            "别太激动，冷静一下，我们一起想想解决办法。",
            "生气伤身体，深呼吸，慢慢来。",
            "我在这里听你倾诉，有什么不满都可以说出来。",
            "我明白你的愤怒，让我们一起冷静分析一下问题。"
        ]
        import random
        return random.choice(responses)
