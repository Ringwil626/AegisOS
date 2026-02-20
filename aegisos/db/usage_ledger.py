"""Usage Ledger - Phase5 AI Usage Accounting.

Single Source of Truth for AI resource consumption.
- Task-level accounting (not per-call)
- Project-based aggregation
- Budget enforcement data source

Tables:
- usage_ledger: All AI usage records
- budgets: Project budget configuration
- rate_limits: Project rate limiting
"""
import os
import sys
import sqlite3
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH


@dataclass
class UsageRecord:
    """Single usage record."""
    task_id: int
    project: str
    model: str
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    latency_ms: int
    cost_estimate: float
    created_at: int


@dataclass
class BudgetConfig:
    """Budget configuration for a project."""
    project: str
    daily_token_limit: Optional[int]
    daily_cost_limit: Optional[float]
    hard_stop: bool = True
    max_tasks_per_minute: int = 10


class UsageLedger:
    """Phase5 AI Usage Accounting - Single Source of Truth."""
    
    @staticmethod
    def init_tables():
        """Initialize usage ledger tables."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Main usage ledger - task-level accounting
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                project TEXT NOT NULL DEFAULT 'aegisos',
                model TEXT NOT NULL,
                tokens_prompt INTEGER NOT NULL DEFAULT 0,
                tokens_completion INTEGER NOT NULL DEFAULT 0,
                tokens_total INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER DEFAULT 0,
                cost_estimate REAL DEFAULT 0.0,
                created_at INTEGER DEFAULT (unixepoch()),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        # Budget configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                project TEXT PRIMARY KEY,
                daily_token_limit INTEGER,
                daily_cost_limit REAL,
                hard_stop BOOLEAN DEFAULT 1,
                max_tasks_per_minute INTEGER DEFAULT 10,
                updated_at INTEGER DEFAULT (unixepoch())
            )
        """)
        
        # Rate limit tracking (sliding window)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rate_limit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                executed_at INTEGER DEFAULT (unixepoch())
            )
        """)
        
        # Create indexes for fast aggregation
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_project_time 
            ON usage_ledger(project, created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_task 
            ON usage_ledger(task_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_rate_limit_project_time 
            ON rate_limit_log(project, executed_at)
        """)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def record_usage(
        task_id: int,
        project: str,
        model: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: int,
        cost_estimate: float
    ) -> int:
        """Record AI usage to ledger.
        
        Phase5: Task-level accounting (not per-call)
        
        Args:
            task_id: Associated task ID
            project: Project identifier
            model: Model name
            tokens_prompt: Input tokens
            tokens_completion: Output tokens
            latency_ms: Execution latency
            cost_estimate: Calculated cost
            
        Returns:
            Ledger entry ID
        """
        # Use runtime_writer for all Level 0 table writes
        from aegisos.db.runtime_writer import record_usage as _record_usage
        
        _record_usage(
            task_id=task_id,
            model=model,
            prompt_tokens=tokens_prompt,
            completion_tokens=tokens_completion,
            cost=cost_estimate
        )
        
        # Rate limiting is also Level 0 - use runtime_writer
        from aegisos.db.runtime_writer import log_rate_limit
        log_rate_limit(project=project, task_id=task_id)
        
        return 0  # ledger_id not available with runtime_writer
        
        return ledger_id
    
    @staticmethod
    def get_project_usage_today(project: str) -> Dict[str, Any]:
        """Get today's usage for a project.
        
        Args:
            project: Project identifier
            
        Returns:
            Usage stats dict
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get start of today (Unix timestamp)
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
        
        cursor.execute("""
            SELECT 
                COUNT(*) as task_count,
                COALESCE(SUM(tokens_total), 0) as total_tokens,
                COALESCE(SUM(cost_estimate), 0) as total_cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency
            FROM usage_ledger
            WHERE project = ?
            AND created_at >= ?
        """, (project, today_start))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "project": project,
            "task_count": row[0],
            "total_tokens": row[1],
            "total_cost": round(row[2], 4),
            "avg_latency_ms": round(row[3], 2)
        }
    
    @staticmethod
    def get_all_projects_usage_today() -> List[Dict[str, Any]]:
        """Get today's usage for all projects."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        today_start = int(datetime.now().replace(hour=0, minute=0, second=0).timestamp())
        
        cursor.execute("""
            SELECT 
                project,
                COUNT(*) as task_count,
                COALESCE(SUM(tokens_total), 0) as total_tokens,
                COALESCE(SUM(cost_estimate), 0) as total_cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency
            FROM usage_ledger
            WHERE created_at >= ?
            GROUP BY project
            ORDER BY total_cost DESC
        """, (today_start,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "project": row[0],
                "task_count": row[1],
                "total_tokens": row[2],
                "total_cost": round(row[3], 4),
                "avg_latency_ms": round(row[4], 2)
            }
            for row in rows
        ]
    
    @staticmethod
    def check_budget(project: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if project is within budget.
        
        Phase5: Budget gate check before AI execution
        
        Args:
            project: Project identifier
            
        Returns:
            (allowed, reason, usage_stats)
        """
        # Get budget config
        budget = UsageLedger.get_budget_config(project)
        
        # Get current usage
        usage = UsageLedger.get_project_usage_today(project)
        
        # Check token limit
        if budget.daily_token_limit and usage["total_tokens"] >= budget.daily_token_limit:
            if budget.hard_stop:
                return False, f"BUDGET_TOKEN_EXCEEDED: {usage['total_tokens']}/{budget.daily_token_limit} tokens", usage
        
        # Check cost limit
        if budget.daily_cost_limit and usage["total_cost"] >= budget.daily_cost_limit:
            if budget.hard_stop:
                return False, f"BUDGET_COST_EXCEEDED: ${usage['total_cost']}/${budget.daily_cost_limit}", usage
        
        return True, "", usage
    
    @staticmethod
    def check_rate_limit(project: str) -> Tuple[bool, str]:
        """Check if project is within rate limit.
        
        Phase5: Rate limiting to prevent AI flooding
        
        Args:
            project: Project identifier
            
        Returns:
            (allowed, reason)
        """
        budget = UsageLedger.get_budget_config(project)
        max_per_minute = budget.max_tasks_per_minute
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Count tasks in last 60 seconds
        one_minute_ago = int(datetime.now().timestamp()) - 60
        
        cursor.execute("""
            SELECT COUNT(*) FROM rate_limit_log
            WHERE project = ?
            AND executed_at >= ?
        """, (project, one_minute_ago))
        
        count = cursor.fetchone()[0]
        conn.close()
        
        if count >= max_per_minute:
            return False, f"RATE_LIMIT_EXCEEDED: {count}/{max_per_minute} tasks per minute"
        
        return True, ""
    
    @staticmethod
    def get_budget_config(project: str) -> BudgetConfig:
        """Get budget configuration for project."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT daily_token_limit, daily_cost_limit, hard_stop, max_tasks_per_minute
            FROM budgets
            WHERE project = ?
        """, (project,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return BudgetConfig(
                project=project,
                daily_token_limit=row[0],
                daily_cost_limit=row[1],
                hard_stop=bool(row[2]),
                max_tasks_per_minute=row[3] or 10
            )
        
        # Default budget
        return BudgetConfig(
            project=project,
            daily_token_limit=None,
            daily_cost_limit=None,
            hard_stop=True,
            max_tasks_per_minute=10
        )
    
    @staticmethod
    def set_budget_config(config: BudgetConfig):
        """Set budget configuration for project."""
        # Use runtime_writer for Level 0 table writes
        from aegisos.db.runtime_writer import update_budget
        update_budget(config.project, 0)  # Initialize with 0 spent
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO budgets
            (project, daily_token_limit, daily_cost_limit, hard_stop, max_tasks_per_minute, updated_at)
            VALUES (?, ?, ?, ?, ?, unixepoch())
        """, (config.project, config.daily_token_limit, config.daily_cost_limit,
              config.hard_stop, config.max_tasks_per_minute))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def get_usage_report(hours: int = 24) -> Dict[str, Any]:
        """Get usage report for time window.
        
        Args:
            hours: Time window in hours
            
        Returns:
            Usage report dict
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        since = int(datetime.now().timestamp()) - (hours * 3600)
        
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT task_id) as task_count,
                COUNT(DISTINCT project) as project_count,
                COALESCE(SUM(tokens_total), 0) as total_tokens,
                COALESCE(SUM(cost_estimate), 0) as total_cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(MAX(latency_ms), 0) as max_latency
            FROM usage_ledger
            WHERE created_at >= ?
        """, (since,))
        
        row = cursor.fetchone()
        conn.close()
        
        return {
            "period_hours": hours,
            "task_count": row[0],
            "project_count": row[1],
            "total_tokens": row[2],
            "total_cost": round(row[3], 4),
            "avg_latency_ms": round(row[4], 2),
            "max_latency_ms": row[5]
        }


class BudgetManager:
    """Budget management - compatibility wrapper around UsageLedger."""
    
    DEFAULT_BUDGETS = {
        "aegisos": {"daily_tokens": 100000, "daily_cost": 5.0},
        "default": {"daily_tokens": 50000, "daily_cost": 2.0}
    }
    
    @staticmethod
    def set_budget(project: str, daily_token_limit: int, daily_cost_limit: float, 
                   hard_stop: bool = True, max_tasks_per_minute: int = 10):
        """Set budget for a project.
        
        Args:
            project: Project name
            daily_token_limit: Daily token limit
            daily_cost_limit: Daily cost limit ($)
            hard_stop: Whether to hard stop when exceeded
            max_tasks_per_minute: Rate limit
        """
        config = BudgetConfig(
            project=project,
            daily_token_limit=daily_token_limit,
            daily_cost_limit=daily_cost_limit,
            hard_stop=hard_stop,
            max_tasks_per_minute=max_tasks_per_minute
        )
        UsageLedger.set_budget_config(config)
    
    @staticmethod
    def check_budget_gate(project: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Check if project is within budget (alias for check_budget).
        
        Returns:
            (allowed, reason, usage_stats)
        """
        return UsageLedger.check_budget(project)


# Convenience functions

def record_task_usage(
    task_id: int,
    project: str,
    model: str,
    tokens_prompt: int,
    tokens_completion: int,
    latency_ms: int,
    cost_estimate: float
) -> int:
    """Convenience function to record usage."""
    return UsageLedger.record_usage(
        task_id=task_id,
        project=project,
        model=model,
        tokens_prompt=tokens_prompt,
        tokens_completion=tokens_completion,
        latency_ms=latency_ms,
        cost_estimate=cost_estimate
    )


def check_project_budget(project: str) -> Tuple[bool, str]:
    """Convenience function to check budget."""
    allowed, reason, _ = UsageLedger.check_budget(project)
    return allowed, reason


def get_today_usage(project: str = "aegisos") -> Dict[str, Any]:
    """Convenience function to get today's usage."""
    return UsageLedger.get_project_usage_today(project)
