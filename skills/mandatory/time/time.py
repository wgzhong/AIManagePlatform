from datetime import datetime, timedelta
from ...base_skill import BaseSkill
from core.reminder_manager import reminder_manager


class GetTimeSkill(BaseSkill):
    name = "get_time"
    description = "获取当前时间，设置提醒、闹钟功能"
    category = "时间工具"
    enabled = True
    auto_trigger = True
    trigger_keywords = ["几点", "时间", "日期", "现在", "提醒", "闹钟", "叫我", "定时"]
    parameters = {
        "type": "object",
        "required": [],
        "properties": {
            "action": {
                "type": "string",
                "description": "操作类型：get_time（获取时间）、set_reminder（设置提醒）、cancel_reminder（取消提醒）、list_reminders（查看提醒列表）",
                "enum": ["get_time", "set_reminder", "cancel_reminder", "list_reminders"]
            },
            "minutes": {
                "type": "integer",
                "description": "N分钟后提醒（仅action=set_reminder时使用）"
            },
            "hour": {
                "type": "integer",
                "description": "指定小时（仅action=set_reminder时使用）"
            },
            "minute": {
                "type": "integer",
                "description": "指定分钟（仅action=set_reminder时使用）"
            },
            "message": {
                "type": "string",
                "description": "提醒消息内容"
            },
            "reminder_id": {
                "type": "string",
                "description": "提醒ID（取消提醒时使用）"
            }
        }
    }

    def run(self, args):
        action = args.get("action", "get_time")

        if action == "get_time":
            return self._get_current_time()
        elif action == "set_reminder":
            return self._set_reminder(args)
        elif action == "cancel_reminder":
            return self._cancel_reminder(args)
        elif action == "list_reminders":
            return self._list_reminders()
        else:
            return f"未知操作：{action}"

    def _get_current_time(self):
        now = datetime.now()
        week_map = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
        week = week_map[now.weekday()]
        return f"当前系统时间：{now.strftime(f'%Y年%m月%d日 {week} %H:%M:%S')}"

    def _set_reminder(self, args):
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
            now = datetime.now()
            trigger_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if trigger_time <= now:
                trigger_time += timedelta(days=1)
            return f"⏰ 已设置闹钟！将在 {trigger_time.strftime('%Y年%m月%d日 %H:%M')} 提醒你：{message}\n提醒ID：{reminder_id}"

        else:
            return "⚠️ 设置提醒失败，请提供 minutes（N分钟后）或 hour+minute（指定时间）参数"

    def _cancel_reminder(self, args):
        reminder_id = args.get("reminder_id")
        if not reminder_id:
            return "⚠️ 请提供提醒ID"

        if reminder_manager.cancel_reminder(reminder_id):
            return f"✅ 已取消提醒：{reminder_id}"
        else:
            return f"❌ 未找到提醒：{reminder_id}"

    def _list_reminders(self):
        reminders = reminder_manager.get_pending_reminders()
        if not reminders:
            return "暂无待执行的提醒"

        result = "📋 待执行的提醒：\n"
        for idx, r in enumerate(reminders, 1):
            trigger_time = datetime.fromisoformat(r['trigger_time'])
            result += f"{idx}. [{r['id']}] {trigger_time.strftime('%Y-%m-%d %H:%M')} - {r['message']}\n"
        return result
