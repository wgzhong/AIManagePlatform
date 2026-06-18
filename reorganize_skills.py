import os
import shutil

# 删除旧的 emotions 目录
if os.path.exists("skills/emotions"):
    shutil.rmtree("skills/emotions")

# 创建新的情绪目录结构
emotions = ["anger", "cheerful", "disgust", "fear", "happy", "sad", "surprise"]
for emotion in emotions:
    os.makedirs(f"skills/emotions/{emotion}", exist_ok=True)

# 创建基础情绪响应技能
anger_content = '''from ...base_skill import BaseSkill

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
'''

cheerful_content = '''from ...base_skill import BaseSkill

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
'''

disgust_content = '''from ...base_skill import BaseSkill

class DisgustSkill(BaseSkill):
    name = "disgust_response"
    description = "当用户表达厌恶情绪时，给予理解和支持"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["恶心", "讨厌", "厌恶", "烦", "想吐", "受不了", "反感"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达厌恶的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "我能理解这种感觉确实让人不舒服。",
            "遇到让人反感的事情确实不好受。",
            "别太在意，让我们把注意力转移到愉快的事情上。",
            "这种情况确实令人不快，希望尽快过去。"
        ]
        import random
        return random.choice(responses)
'''

fear_content = '''from ...base_skill import BaseSkill

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
'''

happy_content = '''from ...base_skill import BaseSkill

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
'''

sad_content = '''from ...base_skill import BaseSkill

class SadSkill(BaseSkill):
    name = "sad_response"
    description = "当用户表达悲伤情绪时，给予安慰和支持"
    category = "情感响应"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["伤心", "难过", "悲伤", "痛苦", "失落", "沮丧", "愁", "哭"]
    
    parameters = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "用户表达悲伤的文本"}
        }
    }
    
    def run(self, args):
        text = args.get("text", "")
        responses = [
            "抱抱你，难过的时候哭出来会好一些。",
            "我理解你的感受，有什么想说的都可以跟我说。",
            "每个人都有难过的时候，这很正常，给自己一些时间。",
            "不要独自承受，我在这里陪着你。",
            "一切都会过去的，明天会更好。"
        ]
        import random
        return random.choice(responses)
'''

surprise_content = '''from ...base_skill import BaseSkill

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
'''

# 写入情绪技能文件
with open("skills/emotions/anger/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .anger import AngerSkill\n\n__all__ = [\"AngerSkill\"]\n")
with open("skills/emotions/anger/anger.py", "w", encoding="utf-8") as f:
    f.write(anger_content)
print("Created skills/emotions/anger/")

with open("skills/emotions/cheerful/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .cheerful import CheerfulSkill\n\n__all__ = [\"CheerfulSkill\"]\n")
with open("skills/emotions/cheerful/cheerful.py", "w", encoding="utf-8") as f:
    f.write(cheerful_content)
print("Created skills/emotions/cheerful/")

with open("skills/emotions/disgust/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .disgust import DisgustSkill\n\n__all__ = [\"DisgustSkill\"]\n")
with open("skills/emotions/disgust/disgust.py", "w", encoding="utf-8") as f:
    f.write(disgust_content)
print("Created skills/emotions/disgust/")

with open("skills/emotions/fear/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .fear import FearSkill\n\n__all__ = [\"FearSkill\"]\n")
with open("skills/emotions/fear/fear.py", "w", encoding="utf-8") as f:
    f.write(fear_content)
print("Created skills/emotions/fear/")

with open("skills/emotions/happy/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .happy import HappySkill\n\n__all__ = [\"HappySkill\"]\n")
with open("skills/emotions/happy/happy.py", "w", encoding="utf-8") as f:
    f.write(happy_content)
print("Created skills/emotions/happy/")

with open("skills/emotions/sad/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .sad import SadSkill\n\n__all__ = [\"SadSkill\"]\n")
with open("skills/emotions/sad/sad.py", "w", encoding="utf-8") as f:
    f.write(sad_content)
print("Created skills/emotions/sad/")

with open("skills/emotions/surprise/__init__.py", "w", encoding="utf-8") as f:
    f.write("from .surprise import SurpriseSkill\n\n__all__ = [\"SurpriseSkill\"]\n")
with open("skills/emotions/surprise/surprise.py", "w", encoding="utf-8") as f:
    f.write(surprise_content)
print("Created skills/emotions/surprise/")

# 更新 emotions 主 __init__.py
emotions_init = '''from .anger import AngerSkill
from .cheerful import CheerfulSkill
from .disgust import DisgustSkill
from .fear import FearSkill
from .happy import HappySkill
from .sad import SadSkill
from .surprise import SurpriseSkill

__all__ = [
    "AngerSkill",
    "CheerfulSkill",
    "DisgustSkill",
    "FearSkill",
    "HappySkill",
    "SadSkill",
    "SurpriseSkill"
]
'''
with open("skills/emotions/__init__.py", "w", encoding="utf-8") as f:
    f.write(emotions_init)
print("Updated skills/emotions/__init__.py")

# 更新主 skills/__init__.py
main_init = '''from .base_skill import BaseSkill

from .mandatory import GetTimeSkill, CalculateSkill

from .emotions import (
    AngerSkill,
    CheerfulSkill,
    DisgustSkill,
    FearSkill,
    HappySkill,
    SadSkill,
    SurpriseSkill
)

ALL_SKILLS = [
    GetTimeSkill(),
    CalculateSkill(),
    AngerSkill(),
    CheerfulSkill(),
    DisgustSkill(),
    FearSkill(),
    HappySkill(),
    SadSkill(),
    SurpriseSkill()
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
    "AngerSkill",
    "CheerfulSkill",
    "DisgustSkill",
    "FearSkill",
    "HappySkill",
    "SadSkill",
    "SurpriseSkill",
    "ALL_SKILLS",
    "get_all_tool_definitions",
    "get_skill_by_name",
    "get_all_skill_configs"
]
'''
with open("skills/__init__.py", "w", encoding="utf-8") as f:
    f.write(main_init)
print("Updated skills/__init__.py")

print("\nDone!")
