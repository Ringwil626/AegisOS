"""AegisOS - Production Hardened Runtime with Kimi API Integration

Phases:
  - Phase 4: Runtime Protocol
  - Phase 5: AI Cost Governance
  - Phase 6: Controlled Evolution
  - Phase 7: Persistent Intelligence
  - Production Hardening: Instance Lock, WAL, Health Monitor, Audit

Kimi API Integration:
  - Set MOONSHOT_API_KEY environment variable to enable real AI
  - Falls back to mock if not configured

Usage:
  python main.py              # Run with mock AI (no API key needed)
  python main.py --demo       # Run demo mode (create test tasks)
  python main.py --cli        # Run interactive CLI mode
"""
import sys
import os
import time
import threading
import atexit
import argparse

sys.path.insert(0, os.path.dirname(__file__))

# P0-1: Instance Lock
from aegisos.core.instancelock import acquire_lock, release_lock

from aegisos.db.sqlite_store import (
    init_db,
    set_system_state,
    get_system_state,
    get_stuck_running_tasks,
    reset_task_to_pending,
    write_audit_log,
    list_evolution_jobs,
    create_task
)
from aegisos.interfaces import discord_bot
from aegisos.executor import task_runner
from aegisos.ai.executor import init_ai_system
from aegisos.ai.kimi_client import KimiClient, check_configuration
from aegisos.evolution.manager import ensure_directories as init_evolution_dirs
from aegisos.memory.vector_index import refresh_index
from aegisos.analysis.outcome_analyzer import auto_analyze_and_save
from aegisos.core.health import update_system_health, record_health_snapshot


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
            
            # Phase 6: Auto-validate evolution proposals (NO AI)
            try:
                from aegisos.evolution.validator import auto_validate_pending
                auto_validate_pending()
            except Exception as e:
                print(f"[Main Loop] Evolution validation error: {e}")
            
            # Phase 7: Analyze completed evolutions and generate memory
            try:
                analyze_completed_evolutions()
            except Exception as e:
                print(f"[Main Loop] Outcome analysis error: {e}")
            
            # Execute one task
            try:
                task_id = task_runner.run_once()
                if task_id:
                    print(f"[Main Loop] Task {task_id} completed")
            except Exception as e:
                print(f"[Main Loop] Execution error: {e}")
        
        time.sleep(10)


def analyze_completed_evolutions():
    """Phase 7: Analyze evolution outcomes and generate engineering memory."""
    jobs = list_evolution_jobs(limit=20)
    
    for job in jobs:
        job_id = job[0]
        status = job[3]
        
        if status in ["validated", "rejected", "approved"]:
            from aegisos.db.sqlite_store import get_memory_by_job_id
            existing = get_memory_by_job_id(job_id)
            
            if not existing:
                print(f"[Phase 7] Analyzing evolution job {job_id}")
                memory_id = auto_analyze_and_save(job_id)
                if memory_id:
                    print(f"[Phase 7] Memory record {memory_id} created")


def graceful_shutdown():
    """P5-2: Graceful shutdown marker."""
    print("\n[Shutdown] Graceful shutdown initiated...")
    set_system_state("last_shutdown", "clean")
    release_lock()
    write_audit_log("system", "shutdown", "success", "Graceful shutdown completed")
    print("[Shutdown] Cleanup complete")


def run_cli_mode():
    """Run interactive CLI mode for testing without Discord."""
    print("\n" + "=" * 70)
    print("AEGISOS CLI MODE")
    print("Commands: status, wake, stop, task <text>, evolve <goal>, exit")
    print("=" * 70 + "\n")
    
    while True:
        try:
            cmd = input("aegisos> ").strip()
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if action == "exit":
                break
            elif action == "status":
                status = get_system_state("status") or "unknown"
                version = get_system_state("runtime_version") or "unknown"
                print(f"Status: {status} | Version: {version}")
            elif action == "wake":
                set_system_state("status", "running")
                print("System started")
            elif action == "stop":
                set_system_state("status", "stopped")
                print("System stopped")
            elif action == "task":
                if arg:
                    task_id = create_task("command", arg)
                    print(f"Task #{task_id} created")
                else:
                    print("Usage: task <text>")
            elif action == "evolve":
                if arg:
                    from aegisos.evolution.manager import create_evolution_proposal
                    proposal_id = create_evolution_proposal(arg)
                    print(f"Evolution proposal {proposal_id} created")
                else:
                    print("Usage: evolve <goal>")
            else:
                print(f"Unknown command: {action}")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("\nExiting CLI mode...")


def run_demo_mode():
    """Create demo tasks for testing."""
    print("\n[DEMO] Creating demo tasks...")
    
    # Create a simple command task
    task1 = create_task("command", "echo Hello from AegisOS")
    print(f"[DEMO] Created task #{task1}: echo Hello from AegisOS")
    
    # Create an AI task (will use mock if no API key)
    task2 = create_task("ai", "ai: Explain what AegisOS does in one sentence")
    print(f"[DEMO] Created task #{task2}: AI explanation task")
    
    # Create an evolution proposal
    from aegisos.evolution.manager import create_evolution_proposal
    proposal = create_evolution_proposal("Add a new CLI command for viewing task statistics")
    print(f"[DEMO] Created evolution proposal: {proposal}")
    
    print("[DEMO] Demo tasks created. Starting system...\n")


def main():
    """Initialize and start AegisOS with production hardening."""
    parser = argparse.ArgumentParser(description="AegisOS - Deterministic Execution Runtime")
    parser.add_argument("--cli", action="store_true", help="Run CLI mode (no Discord)")
    parser.add_argument("--demo", action="store_true", help="Create demo tasks on startup")
    parser.add_argument("--no-discord", action="store_true", help="Run without Discord bot")
    args = parser.parse_args()
    
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
    
    # P0-3: Crash detection
    last_shutdown = get_system_state("last_shutdown")
    if last_shutdown == "clean":
        print("[P0-3] Last shutdown was clean")
        set_system_state("last_start_mode", "clean")
    else:
        print(f"[P0-3] Detected unclean shutdown: {last_shutdown}")
        set_system_state("last_start_mode", "recovered")
        set_system_state("last_shutdown", "unknown")
    
    # Phase 5: Initialize AI ledger
    print("[P1-1] Initializing AI ledger and budget guard...")
    init_ai_system()
    
    # Initialize Kimi API client (if configured)
    print("[P1-2] Checking Kimi API configuration...")
    kimi_ok, kimi_msg = check_configuration()
    if kimi_ok:
        try:
            # Create Kimi client and inject into task runner
            kimi_client = KimiClient(
                api_key=os.getenv("MOONSHOT_API_KEY"),
                base_url=os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
            )
            
            # Replace mock_ai_call with Kimi wrapper
            def kimi_call_wrapper(prompt: str):
                """Wrapper to adapt Kimi client to executor interface."""
                import json
                result = kimi_client.run_task(prompt)
                response_json = json.dumps(result)
                # Estimate tokens (approximate)
                prompt_tokens = len(prompt) // 4
                completion_tokens = len(response_json) // 4
                return response_json, prompt_tokens, completion_tokens
            
            # Inject into task runner
            task_runner.mock_ai_call = kimi_call_wrapper
            print(f"[P1-2] {kimi_msg}")
            print("[OK] Kimi API enabled - AI tasks will use real model")
        except Exception as e:
            print(f"[WARN] Failed to initialize Kimi client: {e}")
            print("[OK] Falling back to mock AI")
    else:
        print(f"[P1-2] {kimi_msg}")
        print("[OK] Using mock AI (set MOONSHOT_API_KEY to enable real API)")
    
    # Phase 6: Initialize evolution workspace
    print("[P2-1] Initializing evolution workspace...")
    init_evolution_dirs()
    
    # Phase 7: Build vector index
    print("[P3-1] Building engineering memory index...")
    refresh_index()
    
    print("[OK] Database ready.")
    
    # Initialize system state
    set_system_state("status", "initialized")
    set_system_state("runtime_version", "v1.0")
    set_system_state("target_version", "")
    
    # P4-2: Audit log startup
    write_audit_log("system", "startup", "success", f"Mode: {mode}")
    
    print("[OK] System initialized.")
    print("=" * 70)
    
    # Demo mode: create test tasks
    if args.demo:
        run_demo_mode()
    
    # CLI mode
    if args.cli:
        # Start Main Loop in background
        print("[OK] Starting Main Loop...")
        loop_thread = threading.Thread(target=main_loop, daemon=True)
        loop_thread.start()
        
        # Run interactive CLI
        run_cli_mode()
        return
    
    # Normal mode with Discord
    if not args.no_discord:
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
        except Exception as e:
            print(f"\n[ERROR] Discord bot failed: {e}")
            print("[INFO] Running in main-loop-only mode...")
            # Keep main loop running even if Discord fails
            while True:
                time.sleep(1)
        finally:
            graceful_shutdown()
    else:
        # Main loop only mode
        print("[OK] Running in main-loop-only mode (no Discord)...")
        set_system_state("status", "running")
        main_loop()


if __name__ == "__main__":
    main()
