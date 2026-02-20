"""AegisOS - Deterministic Runtime

Architecture:
  - Layer 1: Core Runtime (supervisor, executor, db)
  - Layer 2: Execution (task_runner, inference_executor)
  - Layer 3: Interface (discord)
  - Layer 4: Governance (human-approved changes)
  - Layer 5: Project Space (intelligence tools, optional)

Runtime Principles:
  - No AI in Core
  - AI only through inference_executor
  - Deterministic, replayable, auditable
"""
import sys
import os
import time
import threading
import atexit

sys.path.insert(0, os.path.dirname(__file__))

# P0-1: Instance Lock
from aegisos.core.instancelock import acquire_lock, release_lock

# Layer 1: Core Runtime
from aegisos.db.sqlite_store import (
    init_db,
    set_system_state,
    get_system_state,
    get_stuck_running_tasks,
    reset_task_to_pending,
    write_audit_log
)
from aegisos.core.health import update_system_health, record_health_snapshot

# Layer 2: Execution
from aegisos.executor import task_runner

# Layer 3: Interface
from aegisos.interfaces import discord_bot


def main_loop():
    """Main Loop - Execution Gate (tick every 10s)."""
    loop_count = 0
    
    while True:
        status = get_system_state("status") or "stopped"
        
        if status == "running":
            # P0-5: Health check every 30 seconds (every 3 ticks)
            loop_count += 1
            if loop_count % 3 == 0:
                try:
                    update_system_health()
                    record_health_snapshot()
                except Exception as e:
                    print(f"[Main Loop] Health check error: {e}")
            
            # Anti-deadlock
            try:
                stuck = get_stuck_running_tasks(timeout_seconds=3600)
                for task_id in stuck:
                    reset_task_to_pending(task_id)
                    print(f"[Main Loop] Task {task_id} reset (timeout)")
            except Exception as e:
                print(f"[Main Loop] Anti-deadlock error: {e}")
            
            # Execute one task
            try:
                task_id = task_runner.run_once()
                if task_id:
                    print(f"[Main Loop] Task {task_id} completed")
            except Exception as e:
                print(f"[Main Loop] Execution error: {e}")
        
        time.sleep(10)


def graceful_shutdown():
    """P5-2: Graceful shutdown marker."""
    print("\n[Shutdown] Graceful shutdown initiated...")
    set_system_state("last_shutdown", "clean")
    release_lock()
    write_audit_log("system", "shutdown", "success", "Graceful shutdown completed")
    print("[Shutdown] Cleanup complete")


def main():
    """Initialize and start AegisOS with production hardening."""
    print("=" * 70)
    print("AEGISOS PRODUCTION HARDENED STARTUP")
    print("=" * 70)
    
    # P0-1: Acquire instance lock
    locked, mode = acquire_lock()
    if not locked:
        print("[FATAL] Another instance is already running. Exiting.")
        sys.exit(1)
    
    print(f"[P0-1] Instance lock acquired (mode: {mode})")
    
    # Register graceful shutdown
    atexit.register(graceful_shutdown)
    
    # Initialize database
    print("[P0-2] Initializing database with WAL mode...")
    init_db()
    
    # Print firewall status (redundant but explicit)
    print("[GUARD] Runtime Write Firewall: ACTIVE")
    print("[GUARD] Level0 tables protected: 6")
    
    # P0-3: Crash detection
    last_shutdown = get_system_state("last_shutdown")
    if last_shutdown == "clean":
        print("[P0-3] Last shutdown was clean")
        set_system_state("last_start_mode", "clean")
    else:
        print(f"[P0-3] Detected unclean shutdown: {last_shutdown}")
        set_system_state("last_start_mode", "recovered")
        set_system_state("last_shutdown", "unknown")
    
    # Initialize inference executor configuration
    print("[P1-1] Checking inference configuration...")
    from aegisos.executor._inference_provider import check_configuration
    inference_ok, inference_msg = check_configuration()
    print(f"[P1-1] {inference_msg}")
    
    print("[OK] Database ready.")
    
    # Initialize system state
    set_system_state("status", "initialized")
    set_system_state("runtime_version", "v1.0")
    set_system_state("target_version", "")
    
    # P4-2: Audit log startup
    write_audit_log("system", "startup", "success", f"Mode: {mode}")
    
    print("[OK] System initialized.")
    print("=" * 70)
    
    # Start Main Loop
    print("[OK] Starting Main Loop...")
    loop_thread = threading.Thread(target=main_loop, daemon=True)
    loop_thread.start()
    
    # Start Discord bot (blocks forever)
    print("[OK] Starting Discord bot...")
    try:
        discord_bot.run()
    except KeyboardInterrupt:
        print("\n[Interrupt] Received Ctrl+C")
    finally:
        graceful_shutdown()


if __name__ == "__main__":
    main()
