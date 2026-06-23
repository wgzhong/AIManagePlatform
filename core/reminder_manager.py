"""
提醒管理器模块
提供定时提醒功能，支持一次性提醒和重复提醒
支持 SSE 实时推送提醒消息到前端
"""

import uuid
import json
import os
import asyncio
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Any, Optional, List


class ReminderManager:
    """提醒管理器"""

    def __init__(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        self.scheduler = BackgroundScheduler()
        self.reminders: Dict[str, Dict[str, Any]] = {}
        self._data_path = os.path.join(os.path.dirname(__file__), '../data/reminders.json')
        self._load_reminders()
        self._sse_subscribers: List[queue_module.Queue] = []
        self._sse_lock = threading.Lock()
        self._notification_queue = queue_module.Queue()
        self._worker_thread = None
        self._running = False

    def _load_reminders(self):
        """从文件加载提醒"""
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    self.reminders = json.load(f)
            except Exception:
                self.reminders = {}

    def _save_reminders(self):
        """保存提醒到文件"""
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            self._restore_pending_reminders()
            print(f"提醒管理器调度器已启动，当前待执行任务数: {len(self.scheduler.get_jobs())}")
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(target=self._notification_worker, daemon=True)
            self._worker_thread.start()
            print("提醒管理器通知线程已启动")

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=1)
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _notification_worker(self):
        """后台线程处理通知队列"""
        try:
            while self._running:
                try:
                    message = self._notification_queue.get(timeout=0.5)
                    self._notify_all_subscribers(message)
                except queue_module.Empty:
                    continue
                except Exception as e:
                    print(f"通知线程错误: {e}")
                    continue
        finally:
            pass

    def _restore_pending_reminders(self):
        """恢复待执行的提醒"""
        now = datetime.now()
        for reminder_id, reminder in self.reminders.items():
            if reminder['status'] == 'pending':
                trigger_time = datetime.fromisoformat(reminder['trigger_time'])
                if trigger_time > now:
                    self._schedule_reminder(reminder_id, trigger_time)

    def _schedule_reminder(self, reminder_id: str, trigger_time: datetime):
        """调度提醒任务"""
        def callback():
            print(f"触发提醒: {reminder_id}, 当前时间: {datetime.now()}")
            self._trigger_reminder(reminder_id)

        self.scheduler.add_job(
            callback,
            trigger=DateTrigger(run_date=trigger_time),
            id=f"reminder_{reminder_id}",
            replace_existing=True
        )
        print(f"已调度提醒: {reminder_id}, 触发时间: {trigger_time}, 当前时间: {datetime.now()}")

    def _trigger_reminder(self, reminder_id: str):
        """触发提醒"""
        if reminder_id in self.reminders:
            self.reminders[reminder_id]['status'] = 'triggered'
            self.reminders[reminder_id]['triggered_count'] += 1
            self._save_reminders()

            reminder = self.reminders.get(reminder_id)
            if reminder:
                message = {
                    'type': 'reminder',
                    'id': reminder['id'],
                    'message': reminder['message'],
                    'trigger_time': reminder['trigger_time'],
                    'created_at': reminder['created_at']
                }
                print(f"放入通知队列: {message}")
                self._notification_queue.put(message)

    def _notify_all_subscribers(self, message: dict):
        """通知所有 SSE 订阅者（线程安全）"""
        with self._sse_lock:
            print(f"通知订阅者，当前订阅者数: {len(self._sse_subscribers)}")
            closed_queues = []
            for queue in self._sse_subscribers:
                try:
                    queue.put_nowait(message)
                    print("消息已发送到订阅者")
                except Exception as e:
                    print(f"发送消息失败: {e}")
                    closed_queues.append(queue)

            for queue in closed_queues:
                if queue in self._sse_subscribers:
                    self._sse_subscribers.remove(queue)

    async def subscribe(self):
        """订阅 SSE 推送"""
        queue = queue_module.Queue()
        with self._sse_lock:
            self._sse_subscribers.append(queue)
            print(f"新订阅者加入，当前订阅者数: {len(self._sse_subscribers)}")

        try:
            while True:
                message = await asyncio.get_event_loop().run_in_executor(None, queue.get)
                yield message
                queue.task_done()
        except asyncio.CancelledError:
            with self._sse_lock:
                if queue in self._sse_subscribers:
                    self._sse_subscribers.remove(queue)
                    print(f"订阅者离开，当前订阅者数: {len(self._sse_subscribers)}")

    def set_reminder(self, message: str, trigger_time: datetime, repeat_type: str = 'once', 
                     repeat_interval: int = 0, repeat_count: int = 0) -> str:
        """设置提醒"""
        reminder_id = str(uuid.uuid4())[:8]

        reminder = {
            'id': reminder_id,
            'message': message,
            'trigger_time': trigger_time.isoformat(),
            'repeat_type': repeat_type,
            'repeat_interval': repeat_interval,
            'repeat_count': repeat_count,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'triggered_count': 0
        }

        self.reminders[reminder_id] = reminder
        self._save_reminders()
        self._schedule_reminder(reminder_id, trigger_time)

        return reminder_id

    def set_reminder_in_minutes(self, message: str, minutes: int) -> str:
        """设置N分钟后提醒"""
        trigger_time = datetime.now() + timedelta(minutes=minutes)
        return self.set_reminder(message, trigger_time)

    def set_reminder_at_time(self, message: str, hour: int, minute: int, second: int = 0) -> str:
        """设置指定时间提醒（今天或明天）"""
        now = datetime.now()
        trigger_time = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        if trigger_time <= now:
            trigger_time += timedelta(days=1)

        return self.set_reminder(message, trigger_time)

    def cancel_reminder(self, reminder_id: str) -> bool:
        """取消提醒"""
        if reminder_id in self.reminders:
            self.scheduler.remove_job(f"reminder_{reminder_id}", jobstore=None)
            self.reminders[reminder_id]['status'] = 'cancelled'
            self._save_reminders()
            return True
        return False

    def get_reminder(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """获取提醒信息"""
        return self.reminders.get(reminder_id)

    def get_all_reminders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有提醒"""
        reminders = list(self.reminders.values())
        if status:
            reminders = [r for r in reminders if r['status'] == status]
        return sorted(reminders, key=lambda x: x['trigger_time'])

    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """获取待执行的提醒"""
        return self.get_all_reminders('pending')


import queue as queue_module

reminder_manager = ReminderManager()
