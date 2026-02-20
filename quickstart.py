#!/usr/bin/env python3
"""AegisOS Quick Start Verification Script.

Run this to verify the system is ready to use.
"""
import sys
import os

def check():
    print("="*60)
    print("AEGISOS QUICK START VERIFICATION")
    print("="*60)
    print()
    
    all_ok = True
    
    # 1. Dependencies
    print("[1] Checking dependencies...")
    missing = []
    try:
        import discord
        print("  discord.py: OK")
    except ImportError:
        missing.append("discord.py")
        print("  discord.py: NOT FOUND")
        
    try:
        import yaml
        print("  pyyaml: OK")
    except ImportError:
        missing.append("pyyaml")
        print("  pyyaml: NOT FOUND")
        all_ok = False
        
    try:
        import openai
        print("  openai: OK")
    except ImportError:
        print("  openai: NOT FOUND (optional)")
    
    if missing:
        print()
        print("  To install missing packages:")
        print("  pip install " + " ".join(missing))
    
    print()
    
    # 2. Configuration
    print("[2] Checking configuration...")
    if os.path.exists("config.yaml"):
        print("  config.yaml: OK")
    else:
        print("  config.yaml: NOT FOUND")
        all_ok = False
    
    has_discord = bool(os.getenv("DISCORD_TOKEN"))
    has_api_key = bool(os.getenv("MOONSHOT_API_KEY"))
    
    if has_discord:
        print("  DISCORD_TOKEN: SET")
    else:
        print("  DISCORD_TOKEN: NOT SET (Discord bot disabled)")
    
    if has_api_key:
        print("  MOONSHOT_API_KEY: SET")
    else:
        print("  MOONSHOT_API_KEY: NOT SET (AI in mock mode)")
    
    print()
    
    # 3. Database
    print("[3] Testing database...")
    try:
        from aegisos.db.init_all import init_all_tables
        init_all_tables()
        print("  Database: OK")
        
        # Test operations
        from aegisos.db.sqlite_store import create_task, get_task
        import json
        
        task_id = create_task("test", json.dumps({"action": "verify"}), "default")
        task = get_task(task_id)
        
        if task and task["status"] == "pending":
            print("  Task creation: OK")
        else:
            print("  Task creation: FAILED")
            all_ok = False
            
        # Test budget
        from aegisos.db.usage_ledger import BudgetManager
        BudgetManager.set_budget("test", 100000, 5.0)
        allowed, _, _ = BudgetManager.check_budget_gate("test")
        if allowed:
            print("  Budget system: OK")
        else:
            print("  Budget system: WARNING")
            
    except Exception as e:
        print(f"  Database: FAILED - {e}")
        all_ok = False
    
    print()
    print("="*60)
    if all_ok:
        print("STATUS: READY TO USE!")
        print()
        print("Run the system with:")
        print("  python main.py")
    else:
        print("STATUS: NEEDS SETUP")
        print()
        print("Please complete the steps above.")
    print("="*60)
    
    return all_ok

if __name__ == "__main__":
    success = check()
    sys.exit(0 if success else 1)
