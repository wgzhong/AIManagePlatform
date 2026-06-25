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
        self._save_lock = threading.Lock()
        self._reminders_lock = threading.Lock()
        self._load_reminders()
        self._sse_subscribers: List[queue.Queue] = []
        self._sse_lock = threading.Lock()
        self._notification_queue = queue.Queue(maxsize=1000)
        self._worker_thread = None
        self._running = False

    def _load_reminders(self):
        """从文件加载提醒（线程安全）"""
        if os.path.exists(self._data_path):
            try:
                with self._save_lock:
                    with open(self._data_path, 'r', encoding='utf-8') as f:
                        self.reminders = json.load(f)
            except Exception as e:
                logger.warning("加载提醒数据失败: %s", e)
                self.reminders = {}

    def _save_reminders(self):
        """保存提醒到文件（线程安全）"""
        try:
            os.makedirs(os.path.dirname(self._data_path), exist_ok=True)
            with self._save_lock:
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
        """触发提醒，并处理重复调度"""
        with self._reminders_lock:
            if reminder_id not in self.reminders:
                return
            reminder = self.reminders[reminder_id]
            reminder['status'] = 'triggered'
            reminder['triggered_count'] += 1
            self._save_reminders()

        reminder_ref = self.reminders.get(reminder_id)
        if reminder_ref:
            message = {
                'type': 'reminder',
                'id': reminder_ref['id'],
                'message': reminder_ref['message'],
                'trigger_time': reminder_ref['trigger_time'],
                'created_at': reminder_ref['created_at']
            }
            logger.info("放入通知队列: %s", message)
            try:
                self._notification_queue.put(message, timeout=1.0)
            except queue.Full:
                logger.warning("通知队列已满，丢弃提醒: %s", reminder_id)

        # 处理重复提醒
        self._reschedule_if_repeating(reminder_id)

    def _reschedule_if_repeating(self, reminder_id: str):
        """如果提醒配置了重复，重新调度下一次触发"""
        with self._reminders_lock:
            reminder = self.reminders.get(reminder_id)
            if not reminder:
                return
            if reminder.get('repeat_type', 'once') == 'once':
                return
            if reminder.get('repeat_count', 0) > 0 and reminder.get('triggered_count', 0) >= reminder.get('repeat_count', 0):
                return

            old_time = datetime.fromisoformat(reminder['trigger_time'])
            interval = reminder.get('repeat_interval', 0)
            if interval <= 0:
                return

            repeat_type = reminder.get('repeat_type', 'once')
            if repeat_type == 'minutes':
                next_time = old_time + timedelta(minutes=interval)
            elif repeat_type == 'hours':
                next_time = old_time + timedelta(hours=interval)
            elif repeat_type == 'days':
                next_time = old_time + timedelta(days=interval)
            else:
                return

            # 跳过已过去的时间
            now = datetime.now()
            while next_time <= now:
                next_time += timedelta(minutes=interval) if repeat_type == 'minutes' else (
                    timedelta(hours=interval) if repeat_type == 'hours' else timedelta(days=interval))

            reminder['trigger_time'] = next_time.isoformat()
            reminder['status'] = 'pending'
            self._save_reminders()
            self._schedule_reminder(reminder_id, next_time)
            logger.info("重复提醒已重新调度: %s, 下次触发: %s", reminder_id, next_time)

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
        """设置提醒（线程安全）"""
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

        with self._reminders_lock:
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
        """取消提醒（线程安全）"""
        with self._reminders_lock:
            if reminder_id in self.reminders:
                try:
                    self.scheduler.remove_job(f"reminder_{reminder_id}")
                except Exception:
                    logger.exception("移除 APScheduler job 失败: reminder_%s", reminder_id)
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