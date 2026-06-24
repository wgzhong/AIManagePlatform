"""
提醒管理器模块
提供定时提醒功能，支持一次性提醒和重复提醒
支持 SSE 实时推送提醒消息到前端
"""

import uuid
import json
import logging
import os
import asyncio
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from typing import Dict, Any, Optional, List
import queue

logger = logging.getLogger(__name__)


class ReminderManager:
    """提醒管理器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.reminders: Dict[str, Dict[str, Any]] = {}
        self._data_path = os.path.join(os.path.dirname(__file__), '../../data/reminders.json')
        self._load_reminders()
        self._sse_subscribers: List[queue.Queue] = []
        self._sse_lock = threading.Lock()
        self._notification_queue = queue.Queue()
        self._worker_thread = None
        self._running = False

    def _load_reminders(self):
        """从文件加载提醒"""
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path, 'r', encoding='utf-8') as f:
                    self.reminders = json.load(f)
            except Exception as e:
                logger.warning("加载提醒数据失败: %s", e)
                self.reminders = {}

    def _save_reminders(self):
        """保存提醒到文件"""
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with open(self._data_path, 'w', encoding='utf-8') as f:
                json.dump(self.reminders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存提醒数据失败: %s", e)

    def start(self):
        """启动调度器"""
        if not self.scheduler.running:
            self.scheduler.start()
            self._restore_pending_reminders()
            logger.info("提醒管理器调度器已启动，当前待执行任务数: %d", len(self.scheduler.get_jobs()))
        if not self._running:
            self._running = True
            self._worker_thread = threading.Thread(target=self._notification_worker, daemon=True)
            self._worker_thread.start()
            logger.info("提醒管理器通知线程已启动")

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
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.warning("通知线程错误: %s", e)
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
            logger.info("触发提醒: %s, 当前时间: %s", reminder_id, datetime.now())
            self._trigger_reminder(reminder_id)

        self.scheduler.add_job(
            callback,
            trigger=DateTrigger(run_date=trigger_time),
            id=f"reminder_{reminder_id}",
            replace_existing=True
        )
        logger.info("已调度提醒: %s, 触发时间: %s", reminder_id, trigger_time)

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
                logger.info("放入通知队列: %s", message)
                self._notification_queue.put(message)

    def _notify_all_subscribers(self, message: dict):
        """通知所有 SSE 订阅者（线程安全）"""
        with self._sse_lock:
            logger.debug("通知订阅者，当前订阅者数: %d", len(self._sse_subscribers))
            closed_queues = []
            for q in self._sse_subscribers:
                try:
                    q.put_nowait(message)
                    logger.debug("消息已发送到订阅者")
                except Exception as e:
                    logger.warning("发送消息到订阅者失败: %s", e)
                    closed_queues.append(q)

            for q in closed_queues:
                if q in self._sse_subscribers:
                    self._sse_subscribers.remove(q)

    async def subscribe(self):
        """订阅 SSE 推送"""
        q = queue.Queue()
        with self._sse_lock:
            self._sse_subscribers.append(q)
            logger.debug("新订阅者加入，当前订阅者数: %d", len(self._sse_subscribers))

        try:
            loop = asyncio.get_event_loop()
            while True:
                try:
                    message = await loop.run_in_executor(None, lambda: q.get(block=True, timeout=1.0))
                    yield message
                    q.task_done()
                except queue.Empty:
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            with self._sse_lock:
                if q in self._sse_subscribers:
                    self._sse_subscribers.remove(q)
                    logger.debug("订阅者离开，当前订阅者数: %d", len(self._sse_subscribers))

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


reminder_manager = ReminderManager()