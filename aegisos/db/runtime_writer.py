"""Runtime Writer - SINGLE GATEWAY for Level-0 table writes.

System唯一允许修改Level-0表的模块。
"""
import time
from .sqlite_store import get_conn


def create_task(task_type, payload, status="pending"):
    """Create a new task.
    
    Args:
        task_type: Type of task (e.g., 'code_review')
        payload: Task payload JSON
        status: Initial status ('pending', 'running', 'completed')
    """
    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO tasks (type, payload, status, created_at) VALUES (?, ?, ?, ?)",
        (task_type, payload, status, time.time())
    )
    conn.commit()
    return cursor.lastrowid


def update_task_status(task_id, status):
    """Update task status."""
    conn = get_conn()
    conn.execute(
        "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
        (status, time.time(), task_id)
    )
    conn.commit()


def update_task_payload(task_id, payload):
    """Update task payload."""
    conn = get_conn()
    conn.execute(
        "UPDATE tasks SET payload=?, updated_at=? WHERE id=?",
        (payload, time.time(), task_id)
    )
    conn.commit()


def record_usage(task_id, model, prompt_tokens, completion_tokens, cost):
    """Record AI usage to ledger."""
    tokens_total = prompt_tokens + completion_tokens
    conn = get_conn()
    conn.execute(
        """INSERT INTO usage_ledger
        (task_id, model, tokens_prompt, tokens_completion, tokens_total, cost_estimate, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, model, prompt_tokens, completion_tokens, tokens_total, cost, time.time())
    )
    conn.commit()


def write_heartbeat(component, message, runtime_version):
    """Write component heartbeat."""
    conn = get_conn()
    conn.execute(
        "INSERT INTO heartbeats (component, message, runtime_version, timestamp) VALUES (?, ?, ?, ?)",
        (component, message, runtime_version, time.time())
    )
    conn.commit()


def update_budget(project, delta_cost):
    """Update budget spent."""
    conn = get_conn()
    conn.execute(
        "UPDATE budgets SET spent = spent + ? WHERE project=?",
        (delta_cost, project)
    )
    conn.commit()
