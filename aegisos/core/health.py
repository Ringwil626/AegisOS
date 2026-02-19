"""Health Monitor - P0-5 Production Hardening.

Monitors system health and marks degraded state.
Does NOT auto-restart, only marks status.
"""
import time
import sys
import os

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import get_system_state, set_system_state, get_last_heartbeat, DB_PATH

HEARTBEAT_THRESHOLD = 30  # seconds


def check_health() -> dict:
    """Check system health.
    
    Returns:
        {
            'status': 'healthy' | 'degraded',
            'supervisor_alive': bool,
            'last_heartbeat_age': float,
            'details': str
        }
    """
    result = {
        'status': 'healthy',
        'supervisor_alive': True,
        'last_heartbeat_age': 0,
        'details': ''
    }
    
    # Check last heartbeat
    hb = get_last_heartbeat("supervisor")
    if hb:
        last_hb_time = hb.get('timestamp', 0)
        age = time.time() - last_hb_time
        result['last_heartbeat_age'] = age
        
        if age > HEARTBEAT_THRESHOLD:
            result['supervisor_alive'] = False
            result['status'] = 'degraded'
            result['details'] = f"Last heartbeat {age:.0f}s ago (threshold: {HEARTBEAT_THRESHOLD}s)"
    else:
        result['supervisor_alive'] = False
        result['status'] = 'degraded'
        result['details'] = "No heartbeat recorded"
    
    return result


def update_system_health():
    """P0-5: Update system state based on health check.
    
    If heartbeat lost, mark as degraded (do NOT auto-restart).
    """
    health = check_health()
    
    current_status = get_system_state("status")
    
    if health['status'] == 'degraded' and current_status == 'running':
        set_system_state("status", "degraded")
        set_system_state("health_reason", health['details'])
        print(f"[HealthMonitor] System marked as DEGRADED: {health['details']}")
    elif health['status'] == 'healthy' and current_status == 'degraded':
        set_system_state("status", "running")
        set_system_state("health_reason", "")
        print("[HealthMonitor] System recovered to RUNNING")
    
    return health


def record_health_snapshot():
    """P4-3: Record runtime health snapshot for trend analysis."""
    import sqlite3
    
    health = check_health()
    
    # Count pending tasks
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
    queue_depth = cursor.fetchone()[0]
    
    # Simple metrics (would be more complex in production)
    cursor.execute("""
        INSERT INTO runtime_health_snapshot 
        (queue_depth, avg_latency, failure_rate, memory_pressure, supervisor_alive)
        VALUES (?, ?, ?, ?, ?)
    """, (
        queue_depth,
        0.0,  # avg_latency - would measure actual latency
        0.0 if health['status'] == 'healthy' else 1.0,
        0.0,  # memory_pressure - would measure actual memory
        1 if health['supervisor_alive'] else 0
    ))
    
    conn.commit()
    conn.close()
