"""Strategy Manager - Phase6 Strategy Versioning and Switching.

Manages strategy versions with support for:
- Active/Shadow/Retired states
- Strategy switching
- Rollback capability
- Version history

States:
- ACTIVE: Current production strategy
- SHADOW: Under validation
- RETIRED: No longer used but kept for history
"""
import os
import sys
import sqlite3
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH


class StrategyStatus(Enum):
    """Strategy version states."""
    ACTIVE = "active"
    SHADOW = "shadow"
    RETIRED = "retired"


@dataclass
class StrategyVersion:
    """Strategy version data."""
    id: int
    version_tag: str
    config_json: Dict[str, Any]
    status: StrategyStatus
    created_at: datetime
    proposal_id: Optional[int]


class StrategyManager:
    """Manages strategy versions and switching."""
    
    @staticmethod
    def init_tables():
        """Initialize strategy_versions table."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_tag TEXT NOT NULL,
                config_json TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                proposal_id INTEGER,
                FOREIGN KEY (proposal_id) REFERENCES proposals(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def start_shadow_execution(version_id: int):
        """Mark a version as being in shadow testing."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE strategy_versions SET status = 'shadow' WHERE id = ?",
            (version_id,)
        )
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_version(version_tag: str, config: Dict[str, Any],
                      proposal_id: Optional[int] = None) -> int:
        """Create a new strategy version.
        
        Returns:
            Version ID
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO strategy_versions (version_tag, config_json, status, proposal_id)
            VALUES (?, ?, 'shadow', ?)
        """, (version_tag, json.dumps(config), proposal_id))
        
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return version_id
    
    @staticmethod
    def get_active_version() -> Optional[StrategyVersion]:
        """Get currently active strategy version."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, version_tag, config_json, status, created_at, proposal_id
            FROM strategy_versions
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return StrategyVersion(
            id=row[0],
            version_tag=row[1],
            config_json=json.loads(row[2]),
            status=StrategyStatus(row[3]),
            created_at=datetime.fromisoformat(row[4].replace('Z', '+00:00')) if isinstance(row[4], str) else row[4],
            proposal_id=row[5]
        )
    
    @staticmethod
    def switch_to_version(version_id: int) -> bool:
        """Switch to a new strategy version.
        
        Steps:
        1. Retire current active version
        2. Activate new version
        3. Log the switch
        
        Returns:
            True if switch successful
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Check if version exists and is in shadow state
            cursor.execute(
                "SELECT status FROM strategy_versions WHERE id = ?",
                (version_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
            
            # Retire current active
            cursor.execute(
                "UPDATE strategy_versions SET status = 'retired' WHERE status = 'active'"
            )
            
            # Activate new version
            cursor.execute(
                "UPDATE strategy_versions SET status = 'active' WHERE id = ?",
                (version_id,)
            )
            
            if cursor.rowcount == 0:
                conn.rollback()
                conn.close()
                return False
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"[Strategy] Switch error: {e}")
            return False
    
    @staticmethod
    def rollback_to_version(version_id: int) -> bool:
        """Rollback to a previous strategy version.
        
        Args:
            version_id: Version to rollback to (must be retired)
            
        Returns:
            True if rollback successful
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Check if target version exists
            cursor.execute(
                "SELECT id FROM strategy_versions WHERE id = ?",
                (version_id,)
            )
            if not cursor.fetchone():
                conn.close()
                return False
            
            # Retire current active
            cursor.execute(
                "UPDATE strategy_versions SET status = 'retired' WHERE status = 'active'"
            )
            
            # Reactivate old version
            cursor.execute(
                "UPDATE strategy_versions SET status = 'active' WHERE id = ?",
                (version_id,)
            )
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"[Strategy] Rollback error: {e}")
            return False
    
    @staticmethod
    def get_version_history(limit: int = 10) -> List[Dict[str, Any]]:
        """Get strategy version history."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, version_tag, status, created_at, proposal_id
            FROM strategy_versions
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'version_tag': row[1],
                'status': row[2],
                'created_at': row[3],
                'proposal_id': row[4]
            }
            for row in rows
        ]
    
    @staticmethod
    def get_version_by_proposal(proposal_id: int) -> Optional[int]:
        """Get strategy version ID associated with a proposal."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM strategy_versions WHERE proposal_id = ?",
            (proposal_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None


def initialize_default_strategy():
    """Create initial default strategy if none exists."""
    active = StrategyManager.get_active_version()
    if active is None:
        StrategyManager.create_version(
            version_tag="v1.0-default",
            config={
                "prompt_template": "default",
                "model": "kimi-k2.5",
                "temperature": 1.0,
                "max_tokens": 4000
            }
        )
        # Activate it
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE strategy_versions SET status = 'active' WHERE status = 'shadow'"
        )
        conn.commit()
        conn.close()
        print("[Strategy] Created default v1.0 strategy")


def switch_strategy(proposal_id: int) -> bool:
    """Switch strategy based on approved proposal."""
    version_id = StrategyManager.get_version_by_proposal(proposal_id)
    if not version_id:
        return False
    return StrategyManager.switch_to_version(version_id)


def rollback_strategy(version_id: int) -> bool:
    """Rollback to a previous strategy version."""
    return StrategyManager.rollback_to_version(version_id)
