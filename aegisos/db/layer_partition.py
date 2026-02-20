"""Layer Partition - Runtime vs Governance Data Separation.

This module provides explicit separation between:
- RUNTIME LAYER: Deterministic system state (AI cannot write)
- GOVERNANCE LAYER: Human-approved mutations (Runtime cannot write)

Usage:
    # Runtime components use:
    from aegisos.db.layer_partition import RuntimeDB
    
    # Governance components use:
    from aegisos.db.layer_partition import GovernanceDB
"""
import os
import sys
import sqlite3
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database path
DB_PATH = os.path.abspath("aegisos.db")


class RuntimeDB:
    """Runtime Layer Database Access.
    
    For: supervisor, executor, worker, usage accounting
    
    Allowed tables:
        - tasks
        - system_state
        - heartbeats
        - usage_ledger
        - budgets
        - rate_limit_log
    
    FORBIDDEN tables (will raise error):
        - proposals
        - strategy_versions
        - shadow_runs
    """
    
    ALLOWED_TABLES = {
        'tasks', 'system_state', 'heartbeats', 'usage_ledger',
        'budgets', 'rate_limit_log'
    }
    
    FORBIDDEN_TABLES = {
        'proposals', 'strategy_versions', 'shadow_runs'
    }
    
    @classmethod
    @contextmanager
    def connection(cls):
        """Get database connection for Runtime operations."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @classmethod
    def execute(cls, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute SQL with table validation."""
        cls._validate_sql(sql)
        with cls.connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @classmethod
    def execute_write(cls, sql: str, params: tuple = ()) -> int:
        """Execute write operation with strict validation."""
        cls._validate_sql(sql, write=True)
        with cls.connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
    
    @classmethod
    def _validate_sql(cls, sql: str, write: bool = False):
        """Validate SQL against allowed tables."""
        sql_upper = sql.upper()
        
        # Check for forbidden table access
        for table in cls.FORBIDDEN_TABLES:
            if table.upper() in sql_upper:
                raise PermissionError(
                    f"RUNTIME_LAYER_VIOLATION: Runtime attempted to access "
                    f"Governance table '{table}'. "
                    f"Runtime cannot write to Governance layer. "
                    f"Use GovernanceDB for proposals/strategy operations."
                )


class GovernanceDB:
    """Governance Layer Database Access.
    
    For: proposal management, strategy versioning, shadow testing
    
    Allowed tables:
        - proposals
        - strategy_versions
        - shadow_runs
    
    Note: Governance can READ Runtime tables but should not WRITE them.
    """
    
    ALLOWED_TABLES = {
        'proposals', 'strategy_versions', 'shadow_runs'
    }
    
    @classmethod
    @contextmanager
    def connection(cls):
        """Get database connection for Governance operations."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @classmethod
    def execute(cls, sql: str, params: tuple = ()) -> List[Dict]:
        """Execute SQL with table validation."""
        cls._validate_sql(sql)
        with cls.connection() as conn:
            cursor = conn.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @classmethod
    def execute_write(cls, sql: str, params: tuple = ()) -> int:
        """Execute write operation with strict validation."""
        cls._validate_sql(sql, write=True)
        with cls.connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid
    
    @classmethod
    def _validate_sql(cls, sql: str, write: bool = False):
        """Validate SQL for Governance layer."""
        sql_upper = sql.upper()
        
        # Check if trying to write to Runtime tables
        if write:
            runtime_tables = {'TASKS', 'SYSTEM_STATE', 'HEARTBEATS', 'USAGE_LEDGER'}
            for table in runtime_tables:
                # Simple check - look for UPDATE/INSERT/DELETE on runtime tables
                write_ops = ['UPDATE', 'INSERT', 'DELETE']
                for op in write_ops:
                    if op in sql_upper and table in sql_upper:
                        raise PermissionError(
                            f"GOVERNANCE_LAYER_VIOLATION: Governance attempted to "
                            f"write Runtime table '{table}'. "
                            f"Governance cannot corrupt Runtime state. "
                            f"Runtime tables are: supervisor/executor only."
                        )


# Convenience functions for Runtime layer
def runtime_write(table: str, data: dict) -> int:
    """Write to Runtime table (validated)."""
    if table not in RuntimeDB.ALLOWED_TABLES:
        raise PermissionError(f"Table '{table}' not in Runtime layer")
    
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?' for _ in data])
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    
    return RuntimeDB.execute_write(sql, tuple(data.values()))


def runtime_read(table: str, where: str = "", params: tuple = ()) -> List[Dict]:
    """Read from any table (Runtime can read Governance for reference)."""
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return RuntimeDB.execute(sql, params)


# Convenience functions for Governance layer
def governance_write(table: str, data: dict) -> int:
    """Write to Governance table (validated)."""
    if table not in GovernanceDB.ALLOWED_TABLES:
        raise PermissionError(f"Table '{table}' not in Governance layer")
    
    columns = ', '.join(data.keys())
    placeholders = ', '.join(['?' for _ in data])
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    
    return GovernanceDB.execute_write(sql, tuple(data.values()))


def governance_read(table: str, where: str = "", params: tuple = ()) -> List[Dict]:
    """Read from Governance tables."""
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return GovernanceDB.execute(sql, params)


# Table classification documentation
TABLE_LAYERS = {
    # RUNTIME LAYER - Deterministic OS state
    'tasks': 'RUNTIME',
    'system_state': 'RUNTIME',
    'heartbeats': 'RUNTIME',
    'usage_ledger': 'RUNTIME',
    'budgets': 'RUNTIME',
    'rate_limit_log': 'RUNTIME',
    
    # GOVERNANCE LAYER - Human-approved mutations
    'proposals': 'GOVERNANCE',
    'strategy_versions': 'GOVERNANCE',
    'shadow_runs': 'GOVERNANCE',
}


def get_table_layer(table: str) -> str:
    """Get the layer classification for a table."""
    return TABLE_LAYERS.get(table, 'UNKNOWN')


def list_tables_by_layer():
    """List all tables grouped by layer."""
    runtime = [t for t, l in TABLE_LAYERS.items() if l == 'RUNTIME']
    governance = [t for t, l in TABLE_LAYERS.items() if l == 'GOVERNANCE']
    
    print("="*60)
    print("DATABASE LAYER PARTITION")
    print("="*60)
    print()
    print("RUNTIME LAYER (Deterministic - AI cannot write):")
    for t in runtime:
        print(f"  - {t}")
    print()
    print("GOVERNANCE LAYER (Human-approved - Runtime cannot write):")
    for t in governance:
        print(f"  - {t}")
    print()
    print("="*60)


if __name__ == "__main__":
    list_tables_by_layer()
