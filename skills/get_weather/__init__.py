"""
天气查询技能
查询天气信息，包括温度、天气状况、风力等
"""

from typing import Dict, Any
from skills.base_skill import BaseSkill


class WeatherSkill(BaseSkill):
    """天气查询技能"""

    name = "get_weather"
    description = "查询天气信息，包括温度、天气状况、风力等"
    icon = "🌤️"
    category = "工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["天气", "气温", "温度", "下雨", "晴天"]

    parameters = {
        "type": "object",
        "required": [],
        "properties": {
            "city": {"type": "string", "description": "城市名称"}
        }
    }

    def run(self, args: Dict[str, Any]) -> str:
        """执行技能"""
        city = args.get("city", "")
        
        if not city:
            return "⚠️ 请提供城市名称"
        
        try:
            mock_weather = {
                "北京": {"weather": "晴", "temp": 28, "wind": "2级 北风", "humidity": 45},
                "上海": {"weather": "多云", "temp": 32, "wind": "3级 东南风", "humidity": 65},
                "广州": {"weather": "雷阵雨", "temp": 30, "wind": "4级 南风", "humidity": 85},
                "深圳": {"weather": "多云", "temp": 29, "wind": "3级 东风", "humidity": 70},
                "杭州": {"weather": "阴", "temp": 26, "wind": "2级 西北风", "humidity": 60},
                "成都": {"weather": "小雨", "temp": 22, "wind": "1级 东北风", "humidity": 80},
                "重庆": {"weather": "多云", "temp": 24, "wind": "2级 西南风", "humidity": 75},
                "西安": {"weather": "晴", "temp": 30, "wind": "3级 西风", "humidity": 40},
            }
            
            if city in mock_weather:
                w = mock_weather[city]
                return f"""城市：{city}
天气：{w['weather']}
温度：{w['temp']}℃
风力：{w['wind']}
湿度：{w['humidity']}%"""
            else:
                return f"⚠️ 暂不支持查询 {city} 的天气，请尝试其他城市"
        
        except Exception as e:
            return f"❌ 查询失败：{str(e)}"
