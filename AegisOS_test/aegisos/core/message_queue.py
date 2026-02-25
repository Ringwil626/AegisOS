"""Thread-safe message queue for cross-thread communication.

Used for:
- Worker Pool -> Discord Bot (task completion notifications)
- Main Loop -> Discord Bot (system status updates)
"""
import queue
import threading
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class MessageType(Enum):
    TASK_COMPLETE = "task_complete"      # #task-status: 任务执行状态
    SYSTEM_STATUS = "system_status"      # #system-status: 系统运行状态
    ALERT = "alert"                       # #alerts: 告警通知


@dataclass
class DiscordMessage:
    """Message to be sent to Discord."""
    msg_type: MessageType
    channel_id: Optional[str]
    content: str
    embed: Optional[Dict] = None
    task_id: Optional[int] = None


class MessageQueue:
    """Singleton message queue for Discord notifications."""
    
    _instance: Optional["MessageQueue"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._queue = queue.Queue()
        self._initialized = True
    
    def put(self, message: DiscordMessage) -> bool:
        """Add message to queue."""
        try:
            self._queue.put(message, block=False)
            return True
        except queue.Full:
            return False
    
    def get(self, timeout: float = 0.1) -> Optional[DiscordMessage]:
        """Get message from queue (non-blocking with timeout)."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def qsize(self) -> int:
        """Get queue size."""
        return self._queue.qsize()


# Global singleton
def get_message_queue() -> MessageQueue:
    """Get or create MessageQueue singleton."""
    return MessageQueue()


def push_task_notification(task_id: int, task_name: str, project: str, 
                           status: str, result_summary: str, channel_id: str = None):
    """Push task completion notification to queue.
    
    Call this from Worker Pool thread.
    """
    from aegisos.core.message_queue import MessageType, DiscordMessage
    
    status_emoji = "✅" if status == "completed" else "❌"
    project_tag = f"`[{project}]`" if project and project != "default" else ""
    summary = result_summary[:400] + "..." if len(result_summary) > 400 else result_summary
    
    content = (
        f"{status_emoji} **Task #{task_id} {status.upper()}** {project_tag}\n"
        f"📝 {task_name[:100]}\n"
        f"```\n{summary}\n```\n"
        f"Use `/result {task_id}` for details."
    )
    
    msg = DiscordMessage(
        msg_type=MessageType.TASK_COMPLETE,
        channel_id=channel_id,
        content=content,
        task_id=task_id
    )
    
    queue = get_message_queue()
    success = queue.put(msg)
    if success:
        print(f"[MessageQueue] Task #{task_id} notification queued")
    return success


def push_system_notification(status: str, runtime_version: str, active_tasks: int,
                             daily_usage: int, channel_id: str = None):
    """Push system status notification to queue.
    
    Call this from Main Loop thread.
    """
    from aegisos.core.message_queue import MessageType, DiscordMessage
    import time
    
    status_emoji = "🟢" if status == "running" else "🔴"
    
    content = (
        f"{status_emoji} **AegisOS Status** `{runtime_version}`\n"
        f"System: **{status.upper()}**\n"
        f"Active Tasks: {active_tasks} | Daily Tokens: {daily_usage:,}\n"
        f"Last Update: <t:{int(time.time())}:R>"
    )
    
    msg = DiscordMessage(
        msg_type=MessageType.SYSTEM_STATUS,
        channel_id=channel_id,
        content=content
    )
    
    queue = get_message_queue()
    success = queue.put(msg)
    return success


def push_alert_notification(title: str, description: str, level: str = "warning",
                            channel_id: str = None, fields: dict = None):
    """Push alert notification to queue.
    
    Used for critical errors, system anomalies, governance violations.
    Call from anywhere when critical issues occur.
    
    Args:
        title: Alert title
        description: Alert description
        level: 'info' | 'warning' | 'error' | 'critical'
        channel_id: Target Discord channel (optional)
        fields: Additional embed fields dict
    """
    from aegisos.core.message_queue import MessageType, DiscordMessage
    import time
    
    # Color based on level
    colors = {
        "info": 0x3498db,      # Blue
        "warning": 0xf39c12,   # Orange
        "error": 0xe74c3c,     # Red
        "critical": 0x992d22   # Dark Red
    }
    
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨"
    }
    
    embed = {
        "title": f"{emoji.get(level, '⚠️')} {title}",
        "description": description,
        "color": colors.get(level, 0xe74c3c),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "fields": []
    }
    
    if fields:
        for name, value in fields.items():
            embed["fields"].append({
                "name": name,
                "value": str(value)[:1000],  # Discord limit
                "inline": True
            })
    
    content = f"{emoji.get(level, '⚠️')} **Alert**: {title}"
    
    msg = DiscordMessage(
        msg_type=MessageType.ALERT,
        channel_id=channel_id,
        content=content,
        embed=embed
    )
    
    queue = get_message_queue()
    success = queue.put(msg)
    if success:
        print(f"[MessageQueue] Alert '{title}' queued (level: {level})")
    return success
