import os
import shutil

# 创建文件夹结构
folders = ["calculate", "time", "weather"]
for folder in folders:
    os.makedirs(f"skills/mandatory/{folder}", exist_ok=True)

# 获取现有文件内容
with open("skills/mandatory/get_time.py", "r", encoding="utf-8") as f:
    get_time_content = f.read()

with open("skills/mandatory/calculate.py", "r", encoding="utf-8") as f:
    calculate_content = f.read()

# 更新导入路径
get_time_content = get_time_content.replace("from ..base_skill", "from ...base_skill")
calculate_content = calculate_content.replace("from ..base_skill", "from ...base_skill")

# weather 技能内容
weather_content = '''from ...base_skill import BaseSkill

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
            "北京": {"天气": "晴", "温度": "28°C", "风向": "北风", "湿度": "45%"},
            "上海": {"天气": "多云", "温度": "30°C", "风向": "东南风", "湿度": "60%"},
            "广州": {"天气": "小雨", "温度": "32°C", "风向": "南风", "湿度": "85%"},
            "深圳": {"天气": "阴", "温度": "31°C", "风向": "东风", "湿度": "70%"},
            "杭州": {"天气": "晴转多云", "温度": "29°C", "风向": "东北风", "湿度": "55%"},
            "成都": {"天气": "多云", "温度": "26°C", "风向": "西北风", "湿度": "75%"},
            "重庆": {"天气": "小雨", "温度": "25°C", "风向": "西南风", "湿度": "80%"},
            "西安": {"天气": "晴", "温度": "24°C", "风向": "北风", "湿度": "40%"},
        }
        
        if city in weather_data:
            w = weather_data[city]
            return f"{city}今日天气：{w['天气']}，温度{w['温度']}，{w['风向']}，湿度{w['湿度']}"
        else:
            return f"抱歉，暂未查询到{city}的天气信息。支持查询：北京、上海、广州、深圳、杭州、成都、重庆、西安"