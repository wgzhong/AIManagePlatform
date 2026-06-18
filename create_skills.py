import os

# 创建 mandatory 技能
get_time_content = '''from datetime import datetime
from ..base_skill import BaseSkill

class GetTimeSkill(BaseSkill):
    name = "get_time"
    description = "获取当前服务器的年月日、星期、时分秒"
    category = "时间工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["几点", "时间", "日期", "现在"]
    parameters = {"type": "object", "required": [], "properties": {}}
    
    def run(self, args):
        now = datetime.now()
        week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        week = week_map[now.weekday()]
        return f"当前系统时间：{now.strftime(f'%Y年%m月%d日 {week} %H:%M:%S')}"
'''

calculate_content = '''import math
from ..base_skill import BaseSkill

class CalculateSkill(BaseSkill):
    name = "calculate"
    description = "执行数学计算，支持加减乘除等基本运算"
    category = "计算工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["计算", "等于", "+", "-", "*", "/"]
    parameters = {"type": "object", "required": ["expression"], "properties": {"expression": {"type": "string", "description": "数学表达式"}}}
    
    def run(self, args):
        try:
            return f"计算结果：{eval(args.get('expression', ''), {'__builtins__': None}, {'math': math})}"
        except Exception as e:
            return f"计算失败：{str(e)}"
'''

# 创建 emotions 技能
sentiment_analysis_content = '''from ..base_skill import BaseSkill

class SentimentAnalysisSkill(BaseSkill):
    name = "sentiment_analysis"
    description = "分析文本的情感倾向，判断正面、负面或中性"
    category = "情感分析"
    enabled = True
    auto_trigger = False
    trigger_keywords = ["情感", "情绪", "分析", "心情"]
    parameters = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string", "description": "待分析的文本"}}}
    
    def run(self, args):
        text = args.get("text", "")
        positive_words = ["好", "棒", "开心", "高兴", "喜欢", "爱", "美", "赞", "优秀", "精彩", "幸福", "快乐", "满意"]
        negative_words = ["坏", "差", "伤心", "难过", "讨厌", "恨", "丑", "糟", "糟糕", "失望", "痛苦", "愤怒"]
        
        positive_count = sum(1 for word in positive_words if word in text)
        negative_count = sum(1 for word in negative_words if word in text)
        
        if positive_count > negative_count:
            return f"情感分析结果：正面（积极词：{positive_count}个，消极词：{negative_count}个）"
        elif negative_count > positive_count:
            return f"情感分析结果：负面（积极词：{positive_count}个，消极词：{negative_count}个）"
        else:
            return f"情感分析结果：中性（积极词：{positive_count}个，消极词：{negative_count}个）"
'''

emotion_detection_content = '''from ..base_skill import BaseSkill

class EmotionDetectionSkill(BaseSkill):
    name = "emotion_detection"
    description = "检测文本中表达的具体情绪类型"
    category = "情感分析"
    enabled = True
    auto_trigger = False
    trigger_keywords = ["检测", "情绪", "心情", "感受"]
    parameters = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string", "description": "待检测的文本"}}}
    
    def run(self, args):
        text = args.get("text", "")
        
        emotions = {
            "快乐": ["开心", "高兴", "快乐", "幸福", "兴奋", "喜悦", "愉快", "乐", "笑"],
            "悲伤": ["伤心", "难过", "悲伤", "痛苦", "难过", "失落", "沮丧", "愁"],
            "愤怒": ["生气", "愤怒", "火", "怒", "烦", "讨厌", "恨"],
            "惊讶": ["惊讶", "震惊", "哇", "吓", "意外"],
            "恐惧": ["害怕", "恐惧", "怕", "担心", "焦虑"],
            "爱": ["爱", "喜欢", "想念", "思念", "喜欢"]
        }
        
        detected = {}
        for emotion, keywords in emotions.items():
            count = sum(1 for kw in keywords if kw in text)
            if count > 0:
                detected[emotion] = count
        
        if detected:
            result = "检测到的情绪：" + ", ".join([f"{e}({c}次)" for e, c in detected.items()])
            return result
        else:
            return "未检测到明显的情绪表达"
'''

# mandatory __init__.py
mandatory_init = '''from .get_time import GetTimeSkill
from .calculate import CalculateSkill

__all__ = ["GetTimeSkill", "CalculateSkill"]
'''

# emotions __init__.py
emotions_init = '''from .sentiment_analysis import SentimentAnalysisSkill
from .emotion_detection import EmotionDetectionSkill

__all__ = ["SentimentAnalysisSkill", "EmotionDetectionSkill"]
'''

# 主 skills/__init__.py
main_init = '''from .base_skill import BaseSkill

from .mandatory import GetTimeSkill, CalculateSkill

from .emotions import SentimentAnalysisSkill, EmotionDetectionSkill

ALL_SKILLS = [
    GetTimeSkill(),
    CalculateSkill(),
    SentimentAnalysisSkill(),
    EmotionDetectionSkill()
]

def get_all_tool_definitions():
    return [skill.get_tool_schema() for skill in ALL_SKILLS]

def get_skill_by_name(name):
    for skill in ALL_SKILLS:
        if skill.name == name:
            return skill
    return None

def get_all_skill_configs():
    return [skill.get_config_schema() for skill in ALL_SKILLS]

__all__ = [
    "BaseSkill",
    "GetTimeSkill",
    "CalculateSkill",
    "SentimentAnalysisSkill",
    "EmotionDetectionSkill",
    "ALL_SKILLS",
    "get_all_tool_definitions",
    "get_skill_by_name",
    "get_all_skill_configs"
]
'''

# 写入文件
with open("skills/mandatory/get_time.py", "w", encoding="utf-8") as f:
    f.write(get_time_content)
print("Created skills/mandatory/get_time.py")

with open("skills/mandatory/calculate.py", "w", encoding="utf-8") as f:
    f.write(calculate_content)
print("Created skills/mandatory/calculate.py")

with open("skills/emotions/sentiment_analysis.py", "w", encoding="utf-8") as f:
    f.write(sentiment_analysis_content)
print("Created skills/emotions/sentiment_analysis.py")

with open("skills/emotions/emotion_detection.py", "w", encoding="utf-8") as f:
    f.write(emotion_detection_content)
print("Created skills/emotions/emotion_detection.py")

with open("skills/mandatory/__init__.py", "w", encoding="utf-8") as f:
    f.write(mandatory_init)
print("Updated skills/mandatory/__init__.py")

with open("skills/emotions/__init__.py", "w", encoding="utf-8") as f:
    f.write(emotions_init)
print("Created skills/emotions/__init__.py")

with open("skills/__init__.py", "w", encoding="utf-8") as f:
    f.write(main_init)
print("Updated skills/__init__.py")

print("Done!")