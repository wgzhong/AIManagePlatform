import os
import time
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.reminder_manager import reminder_manager

print("启动提醒管理器...")
reminder_manager.start()

print("设置10秒后提醒...")
reminder_id = reminder_manager.set_reminder_in_minutes("测试提醒", 0.2)  # 0.2分钟 = 12秒
print(f"提醒ID: {reminder_id}")

print("等待提醒触发...")
time.sleep(15)

print("检查提醒状态...")
reminder = reminder_manager.get_reminder(reminder_id)
print(f"提醒状态: {reminder.get('status') if reminder else '不存在'}")

print("停止提醒管理器...")
reminder_manager.stop()
print("测试完成!")
