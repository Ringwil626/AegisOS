"""Supervisor - Runtime Transition Protocol v1.0.

Supervisor is the life maintainer and lifecycle controller.
It emits heartbeats and orchestrates task execution.

Key Design:
- Supervisor knows NOTHING about AI
- Supervisor calls Executor (short lifecycle)
- Supervisor is the only loop in the system
- Executor is deterministic state machine driver

Executor Contract v1.0 Relationship:
    Supervisor (loop)
        ↓
    if system_status == running:
        call execute_one_task()
        ↓
    Executor (short lifecycle)
        - Claims one task
        - Executes via Prompt Contract
        - Returns result
        ↓
    Supervisor continues loop

Version: Executor Contract v1.0
"""
import threading
import sys
import os
import time

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import write_heartbeat, set_system_state, get_system_state

# Global state
_thread = None
_stop_event = threading.Event()
_interval = 5  # seconds - heartbeat interval
_executor_enabled = True  # Allow disabling executor for pure supervisor mode


def _execute_task_cycle():
    """Execute one task cycle.
    
    Executor Contract v1.0: Supervisor calls Executor's short-lifecycle
    execute_one_task() function. Executor claims, executes, and returns.
    
    Returns:
        True if a task was executed, False otherwise
    """
    try:
        from aegisos.core.executor import execute_one_task
        
        result = execute_one_task(project="default")
        
        if result:
            print(f"[Supervisor] Task #{result.task_id} {result.status.value} "
                  f"({result.tokens_used} tokens, {result.latency_ms}ms)")
            return True
        else:
            # No pending tasks
            return False
            
    except Exception as e:
        print(f"[Supervisor] Executor error: {e}")
        return False


def _loop():
    """Supervisor heartbeat loop.
    
    Responsibilities:
    1. Emit heartbeat every 5 seconds
    2. Check system status
    3. If running, call Executor for one task cycle
    
    Uses threading.Event for interruptible waits.
    """
    cycle_count = 0
    
    while not _stop_event.is_set():
        # Step 1: Emit heartbeat
        write_heartbeat(component="supervisor", message="alive")
        
        # Step 2: Check system status
        status = get_system_state("status") or "stopped"
        
        # Step 3: If running, execute one task
        if status == "running" and _executor_enabled:
            had_task = _execute_task_cycle()
            
            # If no task, wait full interval
            # If had task, small delay then continue (faster processing)
            if had_task:
                # Brief pause between tasks to prevent CPU spinning
                _stop_event.wait(0.5)
                continue
        
        cycle_count += 1
        
        # Step 4: Wait for next cycle
        _stop_event.wait(_interval)


def start(enable_executor: bool = True):
    """Start supervisor thread.
    
    Sets system_state.status to 'running' and begins:
    - Heartbeat emission
    - Task execution (if executor enabled)
    
    Args:
        enable_executor: If True, supervisor will call Executor
    """
    global _thread, _executor_enabled
    
    if is_running():
        return
    
    _executor_enabled = enable_executor
    _stop_event.clear()
    set_system_state("status", "running")
    
    # Log startup mode
    mode = "with executor" if enable_executor else "supervisor only"
    print(f"[Supervisor] Starting {mode}")
    
    _thread = threading.Thread(target=_loop, daemon=True)
    _thread.start()


def stop():
    """Stop supervisor thread.
    
    Sets system_state.status to 'stopped' and ceases all operations.
    """
    global _thread
    if not is_running():
        return
    
    _stop_event.set()
    if _thread:
        _thread.join(timeout=2)
    set_system_state("status", "stopped")
    print("[Supervisor] Stopped")


def is_running() -> bool:
    """Check if supervisor thread is active."""
    return _thread is not None and _thread.is_alive()


def set_executor_enabled(enabled: bool):
    """Enable/disable executor without stopping supervisor.
    
    Useful for:
    - Maintenance mode (supervisor runs but no task execution)
    - Debugging
    - Graceful shutdown preparation
    
    Args:
        enabled: True to enable executor, False to disable
    """
    global _executor_enabled
    _executor_enabled = enabled
    state = "enabled" if enabled else "disabled"
    print(f"[Supervisor] Executor {state}")


def get_status() -> dict:
    """Get supervisor status.
    
    Returns:
        Dict with supervisor state information
    """
    return {
        "running": is_running(),
        "executor_enabled": _executor_enabled,
        "interval": _interval,
        "system_status": get_system_state("status") or "unknown"
    }
