#!/usr/bin/env python3
"""AegisOS Comprehensive Test Suite

Tests all core modules to ensure everything works out of the box.
"""
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

def test_section(name):
    """Print test section header."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print('='*60)

def test_passed(name):
    """Print test passed message."""
    print(f"  ✓ {name}")

def test_failed(name, error):
    """Print test failed message."""
    print(f"  ✗ {name}: {error}")

def run_tests():
    """Run all tests."""
    passed = 0
    failed = 0
    
    # Test 1: Core Database
    test_section("Database Layer")
    try:
        from aegisos.db.sqlite_store import init_db, create_task, get_task, get_pending_task
        init_db()
        test_passed("init_db()")
        
        task_id = create_task("test", "echo hello")
        test_passed(f"create_task() -> #{task_id}")
        
        task = get_task(task_id)
        assert task is not None
        test_passed("get_task()")
        
        passed += 3
    except Exception as e:
        test_failed("Database", e)
        failed += 3
    
    # Test 2: AI Ledger
    test_section("AI Cost Governance")
    try:
        from aegisos.ai.ledger import init_ai_ledger, check_daily_budget, log_ai_usage, get_budget_report
        init_ai_ledger()
        test_passed("init_ai_ledger()")
        
        allowed, reason = check_daily_budget("kimi", 1000)
        test_passed(f"check_daily_budget() -> allowed={allowed}")
        
        ledger_id = log_ai_usage(1, "kimi", 100, 50, "committed")
        test_passed(f"log_ai_usage() -> #{ledger_id}")
        
        report = get_budget_report()
        assert "hourly" in report
        test_passed("get_budget_report()")
        
        passed += 4
    except Exception as e:
        test_failed("AI Ledger", e)
        failed += 4
    
    # Test 3: AI Executor
    test_section("AI Executor")
    try:
        from aegisos.ai.executor import init_ai_system, execute_with_budget_guard, mock_ai_call
        init_ai_system()
        test_passed("init_ai_system()")
        
        success, response = execute_with_budget_guard(1, "kimi", "test prompt", mock_ai_call)
        test_passed(f"execute_with_budget_guard() -> success={success}")
        
        passed += 2
    except Exception as e:
        test_failed("AI Executor", e)
        failed += 2
    
    # Test 4: Task Runner
    test_section("Task Runner")
    try:
        from aegisos.executor.task_runner import run_once
        
        # Create a pending task
        from aegisos.db.sqlite_store import create_task, get_task
        task_id = create_task("command", "test runner")
        
        # Run it (may return different task_id if queue has other pending tasks)
        result = run_once()
        assert result is not None, "run_once() should return a task_id"
        test_passed(f"run_once() -> #{result}")
        
        # Check the returned task is completed
        task = get_task(result)
        assert task[2] == "completed"
        test_passed("Task completed successfully")
        
        passed += 2
    except Exception as e:
        test_failed("Task Runner", e)
        failed += 2
    
    # Test 5: Instance Lock
    test_section("Instance Lock")
    try:
        from aegisos.core.instancelock import acquire_lock, release_lock, is_locked
        
        # We should already have the lock from main.py
        locked, mode = acquire_lock()
        test_passed(f"acquire_lock() -> locked={locked}, mode={mode}")
        
        passed += 1
    except Exception as e:
        test_failed("Instance Lock", e)
        failed += 1
    
    # Test 6: Health Monitor
    test_section("Health Monitor")
    try:
        from aegisos.core.health import check_health, update_system_health
        
        health = check_health()
        assert "status" in health
        test_passed(f"check_health() -> {health['status']}")
        
        passed += 1
    except Exception as e:
        test_failed("Health Monitor", e)
        failed += 1
    
    # Test 7: Evolution Manager
    test_section("Evolution Manager")
    try:
        from aegisos.evolution.manager import ensure_directories, create_evolution_proposal
        
        ensure_directories()
        test_passed("ensure_directories()")
        
        # Create a test evolution proposal
        proposal_path = create_evolution_proposal(999, "Test evolution proposal")
        assert os.path.exists(proposal_path)
        test_passed(f"create_evolution_proposal() -> {os.path.basename(proposal_path)}")
        
        passed += 2
    except Exception as e:
        test_failed("Evolution Manager", e)
        failed += 2
    
    # Test 8: Vector Index
    test_section("Vector Index")
    try:
        from aegisos.memory.vector_index import refresh_index, get_vector_index
        
        index = refresh_index()
        test_passed("refresh_index()")
        
        idx = get_vector_index()
        assert idx is not None
        test_passed("get_vector_index()")
        
        passed += 2
    except Exception as e:
        test_failed("Vector Index", e)
        failed += 2
    
    # Test 9: Supervisor
    test_section("Supervisor")
    try:
        from aegisos.core.supervisor import is_running, get_status
        
        status = get_status()
        assert "running" in status
        test_passed(f"get_status() -> running={status['running']}")
        
        passed += 1
    except Exception as e:
        test_failed("Supervisor", e)
        failed += 1
    
    # Test 10: Configuration
    test_section("Configuration")
    try:
        import yaml
        
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
        
        assert "discord" in config
        assert "ai" in config
        assert "paths" in config
        test_passed("config.yaml loaded")
        
        passed += 1
    except Exception as e:
        test_failed("Configuration", e)
        failed += 1
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    
    if failed == 0:
        print("\n🎉 All tests passed! AegisOS is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
