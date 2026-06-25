"""
时间工具技能
提供时间查询和定时提醒功能
"""

from datetime import datetime, timedelta
from typing import Dict, Any
from app.skills.base_skill import BaseSkill
from app.core.reminder_manager import reminder_manager


class GetTimeSkill(BaseSkill):
    """时间工具技能"""

    name = "get_time"
    description = (
        "【强制调用】获取当前真实时间/日期/星期。"
        "你没有内置时钟，不知道现在几点、今天几号。"
        "当用户问「几点了」「什么时间」「今天几号」「星期几」「现在什么时候」时，"
        "必须立即调用此工具（action=get_time），禁止猜测或编造时间！"
        "也支持设置提醒（action=set_reminder）和查看/取消已有提醒。"
    )
    icon = "⏰"
    category = "工具"
    enabled = True
    auto_trigger = True
    is_direct_tool = True  # 时间结果直接返回，不需要 LLM 二次总结
    trigger_keywords = ["时间", "几点", "日期", "提醒", "闹钟", "定时", "分钟后", "小时后", "叫我"]

    parameters = {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型：get_time(获取时间)、set_reminder(设置提醒，必须配合minutes或hour+minute参数)、cancel_reminder(取消提醒)、list_reminders(列出提醒)"
            },
            "minutes": {"type": "integer", "description": "多少分钟后提醒，当用户说'一分钟后叫我'、'30分钟后提醒我'等时使用此参数"},
            "hour": {"type": "integer", "description": "提醒时间（小时），用于指定具体时间点"},
            "minute": {"type": "integer", "description": "提醒时间（分钟），用于指定具体时间点"},
            "message": {"type": "string", "description": "提醒消息内容，默认'提醒时间到了！'"},
            "reminder_id": {"type": "string", "description": "要取消的提醒ID"}
        }
    }

    def run(self, args: Dict[str, Any]) -> str:
        """执行技能"""
        action = args.get("action", "get_time")
        
        if action == "get_time" or not action:
            now = datetime.now()
            return f"现在是 {now.strftime('%Y年%m月%d日 %H:%M')}"
        
        elif action == "set_reminder":
            minutes = args.get("minutes")
            hour = args.get("hour")
            minute = args.get("minute")
            message = args.get("message", "提醒时间到了！")
            
            if minutes is not None:
                reminder_id = reminder_manager.set_reminder_in_minutes(message, minutes)
                trigger_time = datetime.now() + timedelta(minutes=minutes)
                return f"⏰ 已设置提醒！将在 {minutes} 分钟后（{trigger_time.strftime('%H:%M')}）提醒你：{message}\n提醒ID：{reminder_id}"
            
            elif hour is not None and minute is not None:
                reminder_id = reminder_manager.set_reminder_at_time(message, hour, minute)
                return f"⏰ 已设置闹钟！将在 {datetime.now().strftime('%Y年%m月%d日')} {hour:02d}:{minute:02d} 提醒你：{message}\n提醒ID：{reminder_id}"
            
            else:
                return "⚠️ 请提供提醒时间（minutes 或 hour+minute）"
        
        elif action == "cancel_reminder":
            reminder_id = args.get("reminder_id")
            if reminder_id:
                if reminder_manager.cancel_reminder(reminder_id):
                    return f"✅ 已取消提醒：{reminder_id}"
                else:
                    return f"❌ 提醒不存在：{reminder_id}"
            else:
                return "⚠️ 请提供提醒ID"
        
        elif action == "list_reminders":
            reminders = reminder_manager.get_pending_reminders()
            if not reminders:
                return "📋 暂无待执行的提醒"
            result = "📋 待执行的提醒：\n"
            for i, r in enumerate(reminders, 1):
                trigger_time = r.get("trigger_time", "")
                msg = r.get("message", "")
                reminder_id = r.get("id", "")
                result += f"{i}. [{reminder_id}] {trigger_time} - {msg}\n"
            return result
        
        else:
            now = datetime.now()
            return f"现在是 {now.strftime('%Y年%m月%d日 %H:%M')}"
