from datetime import datetime
from ...base_skill import BaseSkill

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
