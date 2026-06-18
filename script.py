import os

os.makedirs("skills/mandatory/calculate", exist_ok=True)
os.makedirs("skills/mandatory/time", exist_ok=True)
os.makedirs("skills/mandatory/weather", exist_ok=True)

with open("skills/mandatory/get_time.py", "r", encoding="utf-8") as f:
    get_time_content = f.read()
with open("skills/mandatory/calculate.py", "r", encoding="utf-8") as f:
    calculate_content = f.read()

get_time_content = get_time_content.replace("from ..base_skill", "from ...base_skill")
calculate_content = calculate_content.replace("from ..base_skill", "from ...base_skill")

with open("skills/mandatory/time/__init__.py", "w", encoding="utf-8") as f:
    f.write('from .time import GetTimeSkill\n\n__all__ = ["GetTimeSkill"]\n')
with open("skills/mandatory/time/time.py", "w", encoding="utf-8") as f:
    f.write(get_time_content)
print("Created skills/mandatory/time/")

with open("skills/mandatory/calculate/__init__.py", "w", encoding="utf-8") as f:
    f.write('from .calculate import CalculateSkill\n\n__all__ = ["CalculateSkill"]\n')
with open("skills/mandatory/calculate/calculate.py", "w", encoding="utf-8") as f:
    f.write(calculate_content)
print("Created skills/mandatory/calculate/")

with open("skills/mandatory/weather/__init__.py", "w", encoding="utf-8") as f:
    f.write('from .weather import WeatherSkill\n\n__all__ = ["WeatherSkill"]\n')
with open("skills/mandatory/weather/weather.py", "w", encoding="utf-8") as f:
    f.write("""from ...base_skill import BaseSkill

class WeatherSkill(BaseSkill):
    name = "get_weather"
    description = "获取指定城市的天气信息"
    category = "天气工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["天气", "气温", "温度", "晴", "雨", "雪", "风"]
    
    parameters = {
        "type": "object",
        "required": ["city"],
        "properties": {
            "city": {"type": "string", "description": "城市名称"}
        }
    }
    
    def run(self, args):
        city = args.get("city", "北京")
        weather_data = {
            "北京": {"天气": "晴", "温度": "28C", "风向": "北风", "湿度": "45%"},
            "上海": {"天气": "多云", "温度": "30C", "风向": "东南风", "湿度": "60%"},
            "广州": {"天气": "小雨", "温度": "32C", "风向": "南风", "湿度": "85%"},
            "深圳": {"天气": "阴", "温度": "31C", "风向": "东风", "湿度": "70%"},
            "杭州": {"天气": "晴转多云", "温度": "29C", "风向": "东北风", "湿度": "55%"},
            "成都": {"天气": "多云", "温度": "26C", "风向": "西北风", "湿度": "75%"},
            "重庆": {"天气": "小雨", "温度": "25C", "风向": "西南风", "湿度": "80%"},
            "西安": {"天气": "晴", "温度": "24C", "风向": "北风", "湿度": "40%"},
        }
        if city in weather_data:
            w = weather_data[city]
            return f"{city}今日天气：{w['天气']}，温度{w['温度']}，{w['风向']}，湿度{w['湿度']}"
        else:
            return f"抱歉，暂未查询到{city}的天气信息。支持查询：北京、上海、广州、深圳、杭州、成都、重庆、西安"
""")
print("Created skills/mandatory/weather/")

with open("skills/mandatory/__init__.py", "w", encoding="utf-8") as f:
    f.write('from .calculate import CalculateSkill\nfrom .time import GetTimeSkill\nfrom .weather import WeatherSkill\n\n__all__ = ["CalculateSkill", "GetTimeSkill", "WeatherSkill"]\n')
print("Updated skills/mandatory/__init__.py")

with open("skills/__init__.py", "w", encoding="utf-8") as f:
    f.write("""from .base_skill import BaseSkill

from .mandatory import GetTimeSkill, CalculateSkill, WeatherSkill

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
    WeatherSkill(),
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
    "WeatherSkill",
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
""")
print("Updated skills/__init__.py")

os.remove("skills/mandatory/get_time.py")
os.remove("skills/mandatory/calculate.py")
print("Removed old files")

print("Done!")
