"""SQLite storage layer - Runtime Transition Protocol v1.0.

Database schema aligned with strict runtime protocol.
"""
import sqlite3
import os
import time

DB_PATH = os.path.abspath("aegisos.db")
RUNTIME_VERSION = "v1.0"


def _configure_sqlite_pragmas(conn):
    """P0-2: Configure SQLite for production reliability.
    
    WAL mode + Busy timeout - MUST execute every connection.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    conn.commit()


def init_db():
    """Initialize database with Runtime Transition Protocol v1.0 schema."""
    conn = sqlite3.connect(DB_PATH)
    
    # P0-2: MUST configure WAL every connection
    _configure_sqlite_pragmas(conn)
    
    cursor = conn.cursor()
    
    # Tasks table - Phase 4 compatible
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            status TEXT,
            payload TEXT,
            created_at REAL DEFAULT (unixepoch()),
            updated_at REAL DEFAULT (unixepoch())
        )
    """)
    
    # System state - Runtime Transition Protocol v1.0
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at REAL DEFAULT (unixepoch())
        )
    """)
    
    # Initialize system state with protocol defaults
    defaults = [
        ("status", "initialized"),
        ("runtime_version", RUNTIME_VERSION),
        ("target_version", "")
    ]
    for key, value in defaults:
        cursor.execute(
            "INSERT OR IGNORE INTO system_state (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    # Heartbeats - Runtime Transition Protocol v1.0
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT,
            message TEXT,
            runtime_version TEXT,
            timestamp REAL DEFAULT (unixepoch())
        )
    """)
    
    # Evolution jobs - Phase 6: Controlled Self-Evolution Runtime
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evolution_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            proposal_path TEXT,
            status TEXT,
            created_at REAL DEFAULT (unixepoch()),
            validated_at REAL,
            approved_at REAL
        )
    """)
    
    # Engineering memory - Phase 7: Persistent Intelligence Layer
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS engineering_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evolution_job_id INTEGER,
            context TEXT,
            change_summary TEXT,
            outcome TEXT,
            metrics TEXT,
            created_at REAL DEFAULT (unixepoch()),
            embedding_id TEXT,
            relevance_score REAL DEFAULT 1.0,
            last_used_at REAL
        )
    """)
    
    # P4-2: Audit log for all control commands
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL DEFAULT (unixepoch()),
            actor TEXT,
            action TEXT,
            result TEXT,
            details TEXT
        )
    """)
    
    # P4-3: Runtime health snapshot for trend analysis
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runtime_health_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL DEFAULT (unixepoch()),
            queue_depth INTEGER,
            avg_latency REAL,
            failure_rate REAL,
            memory_pressure REAL,
            supervisor_alive INTEGER
        )
    """)
    
    # P1-1: AI Budget limits
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_budget (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            daily_limit INTEGER DEFAULT 1000000,
            hourly_limit INTEGER DEFAULT 100000,
            per_task_limit INTEGER DEFAULT 100000,
            updated_at REAL DEFAULT (unixepoch())
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO ai_budget (id, daily_limit, hourly_limit, per_task_limit)
        VALUES (1, 1000000, 100000, 100000)
    """)
    
    # P2-1: Switch state tracking for safe version switching
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS switch_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            current_version TEXT DEFAULT 'v1.0',
            next_version TEXT,
            state TEXT DEFAULT 'idle',
            started_at REAL,
            completed_at REAL,
            result TEXT
        )
    """)
    cursor.execute("""
        INSERT OR IGNORE INTO switch_state (id, current_version, state)
        VALUES (1, 'v1.0', 'idle')
    """)
    
    conn.commit()
    conn.close()
    
    # P0-4: Startup repair - reset stuck running tasks
    _startup_repair_stuck_tasks()


def _startup_repair_stuck_tasks():
    """P0-4: Auto-repair tasks stuck in 'running' state from crash."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE tasks 
        SET status = 'pending', updated_at = unixepoch()
        WHERE status = 'running'
    """)
    
    repaired = cursor.rowcount
    conn.commit()
    conn.close()
    
    if repaired > 0:
        print(f"[StartupRepair] Reset {repaired} stuck tasks to pending")


def get_system_state(key: str) -> str | None:
    """Get system state value by key."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def set_system_state(key: str, value: str):
    """Set system state value with timestamp."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, unixepoch())",
        (key, value)
    )
    conn.commit()
    conn.close()


def write_heartbeat(component: str, message: str):
    """Write heartbeat with Runtime Transition Protocol v1.0 format.
    
    Args:
        component: Component name (e.g., 'supervisor')
        message: Heartbeat message (alive, handoff_prepare, etc.)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO heartbeats (component, message, runtime_version, timestamp) VALUES (?, ?, ?, unixepoch())",
        (component, message, RUNTIME_VERSION)
    )
    conn.commit()
    conn.close()


def get_last_heartbeat(component: str) -> dict | None:
    """Get last heartbeat for component."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT component, message, runtime_version, timestamp FROM heartbeats WHERE component = ? ORDER BY timestamp DESC LIMIT 1",
        (component,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "component": row[0],
            "message": row[1],
            "runtime_version": row[2],
            "timestamp": row[3]
        }
    return None


# Task operations - Phase 4 compliant

def create_task(task_type: str, payload: str) -> int:
    """Create a new task with pending status."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (type, status, payload, created_at, updated_at) VALUES (?, 'pending', ?, unixepoch(), unixepoch())",
        (task_type, payload)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_pending_task():
    """Get one pending task (oldest first).
    
    Executor Contract v1.0: Used by Executor to claim task.
    Note: SQLite doesn't support FOR UPDATE, but we use transaction
    isolation and atomic updates to prevent race conditions.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, status, payload, created_at, updated_at FROM tasks WHERE status = 'pending' ORDER BY id ASC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    return row


def claim_pending_task(timeout_seconds: int = 300):
    """Atomically claim one pending task for execution.
    
    Executor Contract v1.0:
    - SELECT pending task
    - UPDATE to running with started_at
    - Return claimed task
    
    This prevents multiple Executors from claiming the same task.
    
    Args:
        timeout_seconds: Timeout window for this task
        
    Returns:
        Task row (id, type, status, payload, created_at, updated_at, started_at)
        or None if no pending tasks
    """
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = 'EXCLUSIVE'  # Ensure atomicity
    cursor = conn.cursor()
    
    try:
        # Find and claim in single transaction
        cursor.execute(
            """UPDATE tasks 
               SET status = 'running', 
                   updated_at = unixepoch(),
                   started_at = unixepoch()
               WHERE id = (
                   SELECT id FROM tasks 
                   WHERE status = 'pending' 
                   ORDER BY id ASC 
                   LIMIT 1
               )
               RETURNING id, type, status, payload, created_at, updated_at, started_at"""
        )
        row = cursor.fetchone()
        conn.commit()
        return row
    except Exception as e:
        conn.rollback()
        print(f"[DB] Claim task error: {e}")
        return None
    finally:
        conn.close()


def update_task_status(task_id: int, status: str):
    """Update task status and timestamp."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status = ?, updated_at = unixepoch() WHERE id = ?",
        (status, task_id)
    )
    conn.commit()
    conn.close()


def append_task_result(task_id: int, new_payload: str):
    """Append result to task payload."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET payload = ?, updated_at = unixepoch() WHERE id = ?",
        (new_payload, task_id)
    )
    conn.commit()
    conn.close()


def get_stuck_running_tasks(timeout_seconds: int = 300):
    """Get running tasks that exceeded timeout.
    
    Executor Contract v1.0: Timeout recovery mechanism.
    Running tasks that exceeded timeout are considered orphaned
    and should be reset to pending for retry.
    
    Args:
        timeout_seconds: Timeout window (default: 300s = 5min)
        
    Returns:
        List of task rows that are stuck
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, type, status, payload, created_at, updated_at, started_at 
           FROM tasks 
           WHERE status = 'running' 
           AND started_at IS NOT NULL
           AND (unixepoch() - started_at) > ?""",
        (timeout_seconds,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def reset_running_tasks_to_pending(timeout_seconds: int = 300):
    """Reset timed-out running tasks back to pending.
    
    Executor Contract v1.0: Called by Executor at startup
    to recover from crashed/killed executions.
    
    Args:
        timeout_seconds: Tasks running longer than this are reset
        
    Returns:
        Number of tasks reset
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE tasks 
           SET status = 'pending',
               updated_at = unixepoch(),
               started_at = NULL
           WHERE status = 'running' 
           AND started_at IS NOT NULL
           AND (unixepoch() - started_at) > ?""",
        (timeout_seconds,)
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def write_execution_log(task_id: int, started_at: int, finished_at: int,
                       success: bool, tokens_used: int, latency_ms: int,
                       error: str = None):
    """Write execution audit log.
    
    Executor Contract v1.0: Records every execution attempt
    for Phase5 cost analysis and governance.
    
    Args:
        task_id: Associated task ID
        started_at: Execution start timestamp
        finished_at: Execution end timestamp
        success: Whether execution succeeded
        tokens_used: Total tokens consumed
        latency_ms: Execution latency
        error: Error message if failed
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure execution_log table exists
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS execution_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            started_at INTEGER NOT NULL,
            finished_at INTEGER NOT NULL,
            success BOOLEAN NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            latency_ms INTEGER DEFAULT 0,
            error TEXT,
            created_at INTEGER DEFAULT (unixepoch())
        )"""
    )
    
    cursor.execute(
        """INSERT INTO execution_log 
           (task_id, started_at, finished_at, success, tokens_used, latency_ms, error)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, started_at, finished_at, success, tokens_used, latency_ms, error)
    )
    conn.commit()
    conn.close()


def get_stuck_running_tasks_legacy(timeout_seconds: int = 3600):
    """Get running tasks that exceeded timeout (legacy version).
    
    Phase 4: Lease-based execution - timeout recovery.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM tasks WHERE status = 'running' AND (unixepoch() - updated_at) > ?",
        (timeout_seconds,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]


def reset_task_to_pending(task_id: int):
    """Reset task to pending (anti-deadlock only)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET status = 'pending', updated_at = unixepoch() WHERE id = ?",
        (task_id,)
    )
    conn.commit()
    conn.close()


def get_task(task_id: int):
    """Get single task by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, status, payload, created_at, updated_at FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def list_tasks(limit: int = 10):
    """List recent tasks."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, type, status, payload, created_at, updated_at FROM tasks ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# Phase 6: Evolution job operations

def create_evolution_job(task_id: int, proposal_path: str) -> int:
    """Create evolution job record.
    
    Args:
        task_id: Associated task ID
        proposal_path: Path to proposal directory
    
    Returns:
        Job ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO evolution_jobs (task_id, proposal_path, status, created_at) VALUES (?, ?, 'proposed', unixepoch())",
        (task_id, proposal_path)
    )
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id


def get_evolution_job(job_id: int):
    """Get evolution job by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, task_id, proposal_path, status, created_at, validated_at, approved_at FROM evolution_jobs WHERE id = ?",
        (job_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def update_evolution_job_status(job_id: int, status: str):
    """Update evolution job status with appropriate timestamp."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status == "validated":
        cursor.execute(
            "UPDATE evolution_jobs SET status = ?, validated_at = unixepoch() WHERE id = ?",
            (status, job_id)
        )
    elif status == "approved":
        cursor.execute(
            "UPDATE evolution_jobs SET status = ?, approved_at = unixepoch() WHERE id = ?",
            (status, job_id)
        )
    else:
        cursor.execute(
            "UPDATE evolution_jobs SET status = ? WHERE id = ?",
            (status, job_id)
        )
    
    conn.commit()
    conn.close()


def list_evolution_jobs(status: str = None, limit: int = 10):
    """List evolution jobs, optionally filtered by status."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if status:
        cursor.execute(
            "SELECT id, task_id, proposal_path, status, created_at, validated_at, approved_at FROM evolution_jobs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit)
        )
    else:
        cursor.execute(
            "SELECT id, task_id, proposal_path, status, created_at, validated_at, approved_at FROM evolution_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    
    rows = cursor.fetchall()
    conn.close()
    return rows


# Phase 7: Engineering Memory operations

def create_memory_record(evolution_job_id: int, context: str, change_summary: str,
                         outcome: str, metrics: str, embedding_id: str = None) -> int:
    """Create engineering memory record.
    
    Only system-generated outcomes are stored.
    AI is NOT allowed to write memory records.
    
    Args:
        evolution_job_id: Associated evolution job
        context: What was the goal
        change_summary: What was changed
        outcome: success / rollback / degraded
        metrics: JSON string of test results, cost delta, etc.
        embedding_id: Reference to vector index
    
    Returns:
        Memory record ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO engineering_memory 
           (evolution_job_id, context, change_summary, outcome, metrics, created_at, embedding_id)
           VALUES (?, ?, ?, ?, ?, unixepoch(), ?)""",
        (evolution_job_id, context, change_summary, outcome, metrics, embedding_id)
    )
    memory_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return memory_id


def get_memory_by_job_id(evolution_job_id: int):
    """Get memory record by evolution job ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, evolution_job_id, context, change_summary, outcome, metrics, created_at, embedding_id FROM engineering_memory WHERE evolution_job_id = ?",
        (evolution_job_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row


def get_all_memories(outcome: str = None, limit: int = 100):
    """Get all memory records, optionally filtered by outcome."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if outcome:
        cursor.execute(
            "SELECT id, evolution_job_id, context, change_summary, outcome, metrics, created_at FROM engineering_memory WHERE outcome = ? ORDER BY created_at DESC LIMIT ?",
            (outcome, limit)
        )
    else:
        cursor.execute(
            "SELECT id, evolution_job_id, context, change_summary, outcome, metrics, created_at FROM engineering_memory ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_task_ledger_summary(task_id: int) -> dict:
    """Get cost summary for a task from ai_ledger.
    
    Used by outcome analyzer to collect evolution costs.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost), 0), COUNT(*) FROM ai_ledger WHERE task_id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_tokens": row[0],
        "total_cost": row[1],
        "call_count": row[2]
    }


def get_memory_statistics():
    """Get statistics about engineering memory."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
            SUM(CASE WHEN outcome = 'rollback' THEN 1 ELSE 0 END) as rollbacks,
            SUM(CASE WHEN outcome = 'degraded' THEN 1 ELSE 0 END) as degraded
        FROM engineering_memory
    """)
    
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total": row[0],
        "successes": row[1],
        "rollbacks": row[2],
        "degraded": row[3]
    }


# P4-2: Audit log operations

def write_audit_log(actor: str, action: str, result: str, details: str = ""):
    """Write audit log entry for all control commands."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO audit_log (actor, action, result, details) VALUES (?, ?, ?, ?)",
        (actor, action, result, details)
    )
    conn.commit()
    conn.close()


def get_recent_audit_logs(limit: int = 50):
    """Get recent audit log entries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT timestamp, actor, action, result, details FROM audit_log ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# P1-1: AI Budget operations

def get_ai_budget() -> dict:
    """Get current AI budget limits."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT daily_limit, hourly_limit, per_task_limit FROM ai_budget WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "daily_limit": row[0],
            "hourly_limit": row[1],
            "per_task_limit": row[2]
        }
    return {"daily_limit": 1000000, "hourly_limit": 100000, "per_task_limit": 100000}


def update_ai_budget(daily: int = None, hourly: int = None, per_task: int = None):
    """Update AI budget limits."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    
    if daily:
        cursor.execute("UPDATE ai_budget SET daily_limit = ?, updated_at = unixepoch() WHERE id = 1", (daily,))
    if hourly:
        cursor.execute("UPDATE ai_budget SET hourly_limit = ?, updated_at = unixepoch() WHERE id = 1", (hourly,))
    if per_task:
        cursor.execute("UPDATE ai_budget SET per_task_limit = ?, updated_at = unixepoch() WHERE id = 1", (per_task,))
    
    conn.commit()
    conn.close()


# P4-3: Runtime health snapshot operations

def get_latest_health_metrics() -> dict:
    """Get latest runtime health metrics for /status display."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get latest snapshot
    cursor.execute("""
        SELECT queue_depth, avg_latency, failure_rate, supervisor_alive, timestamp
        FROM runtime_health_snapshot
        ORDER BY timestamp DESC LIMIT 1
    """)
    row = cursor.fetchone()
    
    # Get counts
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'completed'")
    completed = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM evolution_jobs WHERE status = 'approved'")
    evolutions = cursor.fetchone()[0]
    
    conn.close()
    
    if row:
        return {
            "queue_depth": pending,
            "completed_today": completed,
            "avg_latency": row[1],
            "failure_rate": row[2],
            "supervisor_alive": bool(row[3]),
            "pending_evolutions": evolutions,
            "last_snapshot": row[4]
        }
    
    return {
        "queue_depth": pending,
        "completed_today": completed,
        "avg_latency": 0.0,
        "failure_rate": 0.0,
        "supervisor_alive": True,
        "pending_evolutions": 0,
        "last_snapshot": 0
    }


# P2-1: Switch state operations

def get_switch_state() -> dict:
    """Get current version switch state."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT current_version, next_version, state, started_at, result FROM switch_state WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "current_version": row[0],
            "next_version": row[1],
            "state": row[2],
            "started_at": row[3],
            "result": row[4]
        }
    return {"current_version": "v1.0", "next_version": None, "state": "idle", "started_at": None, "result": None}


def update_switch_state(state: str = None, next_version: str = None, result: str = None):
    """Update switch state."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    
    if state:
        if state == "staging":
            cursor.execute("""
                UPDATE switch_state 
                SET state = ?, next_version = ?, started_at = unixepoch(), completed_at = NULL
                WHERE id = 1
            """, (state, next_version))
        elif state in ["committed", "rolled_back"]:
            cursor.execute("""
                UPDATE switch_state 
                SET state = ?, result = ?, completed_at = unixepoch()
                WHERE id = 1
            """, (state, result))
        else:
            cursor.execute("UPDATE switch_state SET state = ? WHERE id = 1", (state,))
    
    conn.commit()
    conn.close()


# P3-1: Memory decay - update relevance score

def update_memory_relevance(memory_id: int, score_delta: float):
    """Update memory relevance score (decay or boost)."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE engineering_memory SET relevance_score = MAX(0.0, MIN(1.0, relevance_score + ?)), last_used_at = unixepoch() WHERE id = ?",
        (score_delta, memory_id)
    )
    conn.commit()
    conn.close()


def decay_old_memories(decay_factor: float = 0.1):
    """Apply decay to old, unused memories."""
    conn = sqlite3.connect(DB_PATH)
    _configure_sqlite_pragmas(conn)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE engineering_memory 
        SET relevance_score = MAX(0.1, relevance_score - ?)
        WHERE last_used_at < unixepoch() - 2592000
    """, (decay_factor,))
    conn.commit()
    conn.close()
