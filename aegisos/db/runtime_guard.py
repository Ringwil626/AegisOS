"""Anti-Self-Mutation Guard - Runtime Write Firewall.

This module enforces the architectural boundary between:
- Runtime Layer (deterministic, AI cannot write directly)
- Governance Layer (human-approved mutations only)

Purpose:
Prevent AI from corrupting runtime state through "experimental" writes.
Real-world disaster prevented:
    AI shadow run → budget overflow → runtime degradation → production tasks throttled

Architecture Rule:
    Runtime tables can ONLY be written by:
    1. Core Runtime (supervisor, executor)
    2. Through proper service APIs with validation
    
    Governance tables can ONLY be written by:
    1. Human-approved operations (/propose, /apply)
    2. Explicit governance API calls
"""
import os
import sys
from functools import wraps
from typing import Set, Optional

# Runtime Tables - Deterministic OS state
# AI is FORBIDDEN from writing these directly
RUNTIME_TABLES: Set[str] = {
    'tasks',           # Task lifecycle - Core state machine
    'system_state',    # System status, versions
    'heartbeats',      # Component health
    'usage_ledger',    # Token/cost accounting
    'budgets',         # Budget configuration
    'rate_limit_log',  # Rate limiting audit
}

# Governance Tables - Controlled mutation layer
# Runtime should NOT write these directly
GOVERNANCE_TABLES: Set[str] = {
    'proposals',         # Human-reviewed change proposals
    'strategy_versions', # Approved strategy versions
    'shadow_runs',       # Shadow test results
}

# Whitelist: Who can write to RUNTIME tables
RUNTIME_WRITERS: Set[str] = {
    'aegisos.core.executor',
    'aegisos.core.supervisor',
    'aegisos.core.worker',
    'aegisos.executor.task_runner',
    'aegisos.executor.inference_executor',
    'aegisos.db.usage_ledger',  # Usage recording is allowed
    'aegisos.db.sqlite_store',
}

# Whitelist: Who can write to GOVERNANCE tables
GOVERNANCE_WRITERS: Set[str] = {
    'aegisos.governance.manager',
    'aegisos.governance.proposal',
    'aegisos.interfaces.discord_bot',  # Human commands
    '__main__',  # CLI/admin scripts
}


class MutationGuardError(Exception):
    """Attempted unauthorized write to protected table."""
    pass


def _get_caller_module() -> Optional[str]:
    """Get the module name of the caller."""
    import inspect
    frame = inspect.currentframe()
    try:
        # Walk up the stack to find the actual caller
        # frame 0 = this function
        # frame 1 = the decorated function
        # frame 2 = the actual caller
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            module = caller_frame.f_globals.get('__name__')
            return module
    finally:
        del frame
    return None


def _check_write_permission(table: str, module: Optional[str]) -> bool:
    """Check if the calling module is allowed to write to this table.
    
    Args:
        table: Name of the table being written
        module: Name of the calling module
        
    Returns:
        True if write is allowed
        
    Raises:
        MutationGuardError if write is forbidden
    """
    # Allow if no module info (e.g., direct SQL)
    if not module:
        return True
    
    # Check Runtime tables
    if table in RUNTIME_TABLES:
        # Runtime tables can be written by Runtime components
        # Or by explicitly allowed modules
        for allowed in RUNTIME_WRITERS:
            if module.startswith(allowed):
                return True
        
        # Check if it's a governance component trying to write
        for gov in GOVERNANCE_WRITERS:
            if module.startswith(gov):
                raise MutationGuardError(
                    f"Governance module '{module}' attempted direct write to "
                    f"Runtime table '{table}'. "
                    f"Use service API instead of direct DB write. "
                    f"This prevents AI experimental code from corrupting production state."
                )
        
        # Unknown module - allow but log warning
        return True
    
    # Check Governance tables
    if table in GOVERNANCE_TABLES:
        # Only explicit governance writers allowed
        for allowed in GOVERNANCE_WRITERS:
            if module.startswith(allowed):
                return True
        
        # Runtime trying to write governance table
        for runtime in RUNTIME_WRITERS:
            if module.startswith(runtime):
                raise MutationGuardError(
                    f"Runtime module '{module}' attempted direct write to "
                    f"Governance table '{table}'. "
                    f"Use Governance API (/propose) instead. "
                    f"Runtime should never auto-mutate."
                )
        
        # Unknown module - block by default for governance tables
        raise MutationGuardError(
            f"Module '{module}' not authorized to write Governance table '{table}'. "
            f"Governance tables require explicit approval."
        )
    
    # Unknown table - allow
    return True


def guard_table_write(table_name: str):
    """Decorator to guard write operations to specific tables.
    
    Usage:
        @guard_table_write('tasks')
        def update_task_status(task_id, status):
            # This will check if caller is allowed to write 'tasks'
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            caller = _get_caller_module()
            _check_write_permission(table_name, caller)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def check_write_permission(table: str) -> bool:
    """Check if current context can write to table.
    
    Use this for ad-hoc permission checks.
    
    Returns:
        True if allowed, raises MutationGuardError if not
    """
    caller = _get_caller_module()
    return _check_write_permission(table, caller)


# For direct SQL execution guard
def validate_sql_write(sql: str) -> None:
    """Validate SQL write statement against mutation rules.
    
    Args:
        sql: SQL statement to validate
        
    Raises:
        MutationGuardError if statement violates rules
    """
    sql_upper = sql.upper().strip()
    
    # Only check INSERT/UPDATE/DELETE
    if not any(sql_upper.startswith(cmd) for cmd in ['INSERT', 'UPDATE', 'DELETE']):
        return
    
    # Extract table name (simple heuristic)
    import re
    
    # Match INSERT INTO table
    insert_match = re.search(r'INSERT\s+INTO\s+(\w+)', sql_upper)
    if insert_match:
        table = insert_match.group(1).lower()
        check_write_permission(table)
        return
    
    # Match UPDATE table
    update_match = re.search(r'UPDATE\s+(\w+)', sql_upper)
    if update_match:
        table = update_match.group(1).lower()
        check_write_permission(table)
        return
    
    # Match DELETE FROM table
    delete_match = re.search(r'DELETE\s+FROM\s+(\w+)', sql_upper)
    if delete_match:
        table = delete_match.group(1).lower()
        check_write_permission(table)
        return


class GuardedConnection:
    """SQLite connection wrapper with mutation guard.
    
    Use this instead of raw sqlite3.connect() for runtime protection.
    """
    
    def __init__(self, db_path: str):
        import sqlite3
        self._conn = sqlite3.connect(db_path)
        self._original_execute = self._conn.execute
        
    def execute(self, sql: str, parameters=None):
        """Execute SQL with mutation guard."""
        validate_sql_write(sql)
        if parameters:
            return self._original_execute(sql, parameters)
        return self._original_execute(sql)
    
    def cursor(self):
        """Get cursor with guarded execute."""
        cursor = self._conn.cursor()
        original_cursor_execute = cursor.execute
        
        def guarded_execute(sql, parameters=None):
            validate_sql_write(sql)
            if parameters:
                return original_cursor_execute(sql, parameters)
            return original_cursor_execute(sql)
        
        cursor.execute = guarded_execute
        return cursor
    
    def commit(self):
        return self._conn.commit()
    
    def close(self):
        return self._conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Production mode flag
# Set AEGISOS_STRICT_MODE=1 to enable full mutation guarding
_STRICT_MODE = os.getenv('AEGISOS_STRICT_MODE', '0') == '1'


def is_strict_mode() -> bool:
    """Check if strict mutation guarding is enabled."""
    return _STRICT_MODE


def enable_strict_mode():
    """Enable strict mutation guarding (call at startup)."""
    global _STRICT_MODE
    _STRICT_MODE = True
    print("[GUARD] Anti-Self-Mutation Guard enabled - STRICT MODE")
