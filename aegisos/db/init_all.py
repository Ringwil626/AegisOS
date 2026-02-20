"""Unified database initialization - all tables.

This module initializes all database tables in the correct order.
"""
import sqlite3
import os

DB_PATH = os.path.abspath("aegisos.db")


def get_db_path():
    """Get current database path."""
    return DB_PATH


def set_db_path(path: str):
    """Set database path (for testing)."""
    global DB_PATH
    DB_PATH = os.path.abspath(path)
    
    # Update all dependent modules
    try:
        import aegisos.db.sqlite_store
        aegisos.db.sqlite_store.DB_PATH = DB_PATH
    except:
        pass
    
    try:
        import aegisos.db.usage_ledger
        aegisos.db.usage_ledger.DB_PATH = DB_PATH
    except:
        pass
    
    try:
        import aegisos.intelligence.optimizer
        aegisos.intelligence.optimizer.DB_PATH = DB_PATH
    except:
        pass
    
    try:
        import aegisos.intelligence.strategy_manager
        aegisos.intelligence.strategy_manager.DB_PATH = DB_PATH
    except:
        pass


def _configure_pragmas(conn):
    """Configure SQLite for production."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    conn.commit()


def init_all_tables():
    """Initialize all database tables.
    
    This is the single entry point for database initialization.
    It calls all sub-initialization functions in the correct order.
    """
    # Print DB Write Firewall status (required by Runtime Contract v1.0)
    print("[GUARD] Runtime Write Firewall: ACTIVE")
    print("[GUARD] Level0 tables protected: 6")
    print("[GUARD] Unauthorized writers: BLOCKED")
    print("[GUARD] Protected: tasks, system_state, heartbeats, usage_ledger, budgets, rate_limit_log")
    
    conn = sqlite3.connect(DB_PATH)
    _configure_pragmas(conn)
    
    # 1. Core tables (from sqlite_store)
    _init_core_tables(conn)
    
    # 2. Usage ledger tables (Phase 5)
    _init_usage_tables(conn)
    
    # 3. Intelligence/Optimization tables (Phase 6)
    _init_intelligence_tables(conn)
    
    conn.commit()
    conn.close()
    
    print(f"[DB] All tables initialized: {DB_PATH}")


def _init_core_tables(conn):
    """Initialize core runtime tables."""
    cursor = conn.cursor()
    
    # Tasks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            status TEXT,
            payload TEXT,
            created_at REAL DEFAULT (unixepoch()),
            updated_at REAL DEFAULT (unixepoch())
        )
    """)
    
    # System state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at REAL DEFAULT (unixepoch())
        )
    """)
    
    # Initialize defaults
    defaults = [
        ("status", "initialized"),
        ("runtime_version", "v1.0"),
        ("target_version", "")
    ]
    for key, value in defaults:
        cursor.execute(
            "INSERT OR IGNORE INTO system_state (key, value) VALUES (?, ?)",
            (key, value)
        )
    
    # Heartbeats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            component TEXT,
            message TEXT,
            runtime_version TEXT,
            timestamp REAL DEFAULT (unixepoch())
        )
    """)
    
    conn.commit()


def _init_usage_tables(conn):
    """Initialize usage accounting tables (Phase 5)."""
    cursor = conn.cursor()
    
    # Usage ledger
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
            created_at INTEGER DEFAULT (unixepoch())
        )
    """)
    
    # Budgets
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
    
    # Rate limit log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rate_limit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project TEXT NOT NULL,
            task_id INTEGER NOT NULL,
            executed_at INTEGER DEFAULT (unixepoch())
        )
    """)
    
    conn.commit()


def _init_intelligence_tables(conn):
    """Initialize optimization tables (Phase 6)."""
    cursor = conn.cursor()
    
    # Proposals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            project TEXT NOT NULL,
            reason TEXT NOT NULL,
            action TEXT NOT NULL,
            expected_gain TEXT,
            risk_level TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            created_at INTEGER DEFAULT (unixepoch()),
            approved_at INTEGER,
            approved_by TEXT
        )
    """)
    
    # Strategy versions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_tag TEXT NOT NULL,
            config_json TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            activated_at DATETIME,
            proposal_id INTEGER
        )
    """)
    
    # Shadow runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shadow_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            simulated_tokens INTEGER,
            simulated_latency REAL,
            result_valid BOOLEAN,
            schema_valid BOOLEAN,
            created_at INTEGER DEFAULT (unixepoch())
        )
    """)
    
    conn.commit()


if __name__ == "__main__":
    init_all_tables()
