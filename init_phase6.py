"""Initialize Phase6 Governed Optimization.

Run this script to set up all Phase6 tables and default data.
"""
import sys
sys.path.insert(0, '.')

print("="*70)
print("AEGISOS Phase6 - Governed Optimization Initialization")
print("="*70)

# 1. Create policy.yaml if not exists
print("\n[1/5] Setting up policy configuration...")
from aegisos.intelligence.policy_loader import PolicyLoader
PolicyLoader.create_default_policy()
print("  [OK] Policy configuration ready")

# 2. Initialize tables
print("\n[2/5] Initializing database tables...")

from aegisos.intelligence.optimizer import ProposalManager
ProposalManager.init_tables()
print("  ✓ proposals table")

from aegisos.intelligence.strategy_manager import StrategyManager
StrategyManager.init_tables()
print("  ✓ strategy_versions table")

from aegisos.intelligence.shadow_runner import ShadowRunner
ShadowRunner().init_tables()
print("  ✓ shadow_runs table")

# 3. Create default strategy
print("\n[3/5] Creating default strategy...")
from aegisos.intelligence.strategy_manager import initialize_default_strategy
initialize_default_strategy()

# 4. Initialize usage_ledger if needed
print("\n[4/5] Initializing usage ledger...")
from aegisos.db.usage_ledger import UsageLedger
UsageLedger.init_tables()
print("  ✓ usage_ledger tables")

# 5. Verify setup
print("\n[5/5] Verification...")

# Check tables exist
import sqlite3
from aegisos.db.sqlite_store import DB_PATH

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

tables = ['proposals', 'strategy_versions', 'shadow_runs', 'usage_ledger']
for table in tables:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    if cursor.fetchone():
        print(f"  ✓ {table}")
    else:
        print(f"  ✗ {table} NOT FOUND")

conn.close()

print("\n" + "="*70)
print("Phase6 Initialization Complete!")
print("="*70)
print("\nPhase6 Components:")
print("  ✓ Analyzer - Behavior observation (4 key metrics)")
print("  ✓ Evaluator - Optimization decision (policy-based)")
print("  ✓ Optimizer - Proposal generation (no auto-execution)")
print("  ✓ Shadow Runner - Validation without production impact")
print("  ✓ Strategy Manager - Versioning with switch/rollback")
print("\nDiscord Commands:")
print("  /proposals list - View pending proposals")
print("  /proposals approve <id> - Approve proposal")
print("  /strategy switch <proposal_id> - Switch strategy")
print("  /strategy rollback <version_id> - Rollback strategy")
print("\nGovernance Rules:")
print("  ✗ NO automatic execution")
print("  ✗ NO AI modifying prompt directly")
print("  ✗ NO auto-switching models")
print("  ✓ Human approval required")
print("  ✓ Shadow validation before switch")
print("  ✓ Rollback always available")
