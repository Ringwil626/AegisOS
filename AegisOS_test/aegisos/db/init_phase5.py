"""Initialize Phase5 AI Usage Accounting.

Run this to set up Phase5 tables and default budgets.
"""
import os
import sys

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.usage_ledger import UsageLedger, BudgetConfig


def init_phase5():
    """Initialize Phase5 tables and default budgets."""
    print("Initializing Phase5 AI Usage Accounting...")
    
    # Initialize tables
    UsageLedger.init_tables()
    print("  ✓ Tables created")
    
    # Set default budgets
    default_budgets = [
        BudgetConfig(
            project="aegisos",
            daily_token_limit=100000,      # 100K tokens
            daily_cost_limit=5.0,          # $5 USD
            hard_stop=True,
            max_tasks_per_minute=5
        ),
        BudgetConfig(
            project="default",
            daily_token_limit=50000,       # 50K tokens
            daily_cost_limit=2.0,          # $2 USD
            hard_stop=True,
            max_tasks_per_minute=3
        ),
    ]
    
    for budget in default_budgets:
        UsageLedger.set_budget_config(budget)
        print(f"  ✓ Budget set for {budget.project}")
    
    print("\nPhase5 initialization complete!")
    print("\nDefault budgets:")
    print("  aegisos:  $5/day, 100K tokens/day")
    print("  default:  $2/day, 50K tokens/day")


if __name__ == "__main__":
    init_phase5()
