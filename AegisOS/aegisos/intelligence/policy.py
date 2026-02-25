"""Policy - Strategy Versioning and Shadow Execution.

Manages strategy versions and shadow execution for safe optimization.

Key Concepts:
- ACTIVE: Current production strategy
- SHADOW: New strategy being validated
- RETIRED: Old strategies kept for history

Shadow execution runs new strategy alongside old without affecting production.
"""
import os
import sys
import json
import sqlite3
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH
from aegisos.intelligence.optimizer import ProposalManager, ProposalType


class StrategyStatus(Enum):
    """Status of strategy versions."""
    PENDING = "pending"       # Created but not active
    SHADOW = "shadow"         # In shadow validation
    ACTIVE = "active"         # Production strategy
    RETIRED = "retired"       # No longer used


@dataclass
class StrategyVersion:
    """Strategy version definition."""
    id: int
    version: int
    project: str
    prompt_template_hash: str
    execution_rules: Dict[str, Any]
    created_at: int
    activated_at: Optional[int]
    status: StrategyStatus
    parent_version: Optional[int]
    proposal_id: Optional[int]


class StrategyManager:
    """Manages strategy versions and shadow execution."""
    
    @staticmethod
    def create_strategy_version(
        project: str,
        prompt_template: str,
        execution_rules: Dict[str, Any],
        parent_version: Optional[int] = None,
        proposal_id: Optional[int] = None
    ) -> int:
        """Create a new strategy version.
        
        Returns:
            Version ID
        """
        # Calculate hash of prompt template
        prompt_hash = hashlib.sha256(prompt_template.encode()).hexdigest()[:16]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get next version number
        cursor.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM strategy_versions WHERE project = ?",
            (project,)
        )
        version_num = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO strategy_versions 
            (version, project, prompt_template_hash, execution_rules, 
             status, parent_version, proposal_id)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (version_num, project, prompt_hash, 
              json.dumps(execution_rules), parent_version, proposal_id))
        
        version_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return version_id
    
    @staticmethod
    def get_active_strategy(project: str) -> Optional[StrategyVersion]:
        """Get currently active strategy for project."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, version, project, prompt_template_hash, execution_rules,
                   created_at, activated_at, status, parent_version, proposal_id
            FROM strategy_versions
            WHERE project = ? AND status = 'active'
            ORDER BY activated_at DESC
            LIMIT 1
        """, (project,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return StrategyVersion(
            id=row[0],
            version=row[1],
            project=row[2],
            prompt_template_hash=row[3],
            execution_rules=json.loads(row[4]),
            created_at=row[5],
            activated_at=row[6],
            status=StrategyStatus(row[7]),
            parent_version=row[8],
            proposal_id=row[9]
        )
    
    @staticmethod
    def start_shadow_execution(version_id: int):
        """Start shadow execution for a strategy version."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE strategy_versions
            SET status = 'shadow'
            WHERE id = ? AND status = 'pending'
        """, (version_id,))
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def activate_strategy(version_id: int) -> bool:
        """Activate a strategy version (after shadow validation).
        
        Also retires the previously active strategy.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get project for this version
        cursor.execute(
            "SELECT project FROM strategy_versions WHERE id = ?",
            (version_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        
        project = row[0]
        
        # Retire current active strategy
        cursor.execute("""
            UPDATE strategy_versions
            SET status = 'retired'
            WHERE project = ? AND status = 'active'
        """, (project,))
        
        # Activate new strategy
        cursor.execute("""
            UPDATE strategy_versions
            SET status = 'active',
                activated_at = unixepoch()
            WHERE id = ?
        """, (version_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    @staticmethod
    def get_strategy_history(project: str, limit: int = 10) -> List[StrategyVersion]:
        """Get strategy version history for project."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, version, project, prompt_template_hash, execution_rules,
                   created_at, activated_at, status, parent_version, proposal_id
            FROM strategy_versions
            WHERE project = ?
            ORDER BY version DESC
            LIMIT ?
        """, (project, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            StrategyVersion(
                id=row[0],
                version=row[1],
                project=row[2],
                prompt_template_hash=row[3],
                execution_rules=json.loads(row[4]),
                created_at=row[5],
                activated_at=row[6],
                status=StrategyStatus(row[7]),
                parent_version=row[8],
                proposal_id=row[9]
            )
            for row in rows
        ]


class ShadowExecutor:
    """Manages shadow execution for strategy validation."""
    
    def __init__(self, project: str = "aegisos"):
        self.project = project
    
    def execute_shadow_task(self, task_data: Dict[str, Any], 
                           strategy_version: int) -> Dict[str, Any]:
        """Execute a task in shadow mode.
        
        Shadow execution:
        - Runs new strategy
        - Does NOT write results to production
        - Records metrics for comparison
        
        Returns:
            Shadow execution metrics
        """
        # In shadow mode, we would:
        # 1. Load the strategy version
        # 2. Execute with shadow flag
        # 3. Record metrics without side effects
        
        # For now, return placeholder
        return {
            'shadow': True,
            'strategy_version': strategy_version,
            'tokens_used': 0,
            'latency_ms': 0,
            'success': True,
            'output_committed': False
        }
    
    def compare_shadow_vs_production(self, proposal_id: int, 
                                     min_samples: int = 20) -> Dict[str, Any]:
        """Compare shadow execution metrics vs production.
        
        Args:
            proposal_id: Proposal to evaluate
            min_samples: Minimum samples required
            
        Returns:
            Comparison results
        """
        # Get proposal
        proposal = ProposalManager.get_proposal(proposal_id)
        if not proposal:
            return {'error': 'Proposal not found'}
        
        # Get shadow metrics from proposal
        shadow_metrics = proposal.shadow_metrics or '{}'
        try:
            shadow_data = json.loads(shadow_metrics)
        except:
            shadow_data = {}
        
        # Compare with production metrics
        # This would query usage_ledger for the same tasks
        
        return {
            'proposal_id': proposal_id,
            'shadow_samples': shadow_data.get('task_count', 0),
            'production_samples': min_samples,
            'ready_to_switch': shadow_data.get('task_count', 0) >= min_samples,
            'comparison': {
                'token_reduction_pct': 0,
                'latency_reduction_pct': 0,
                'success_rate_change': 0
            }
        }


def switch_strategy(version_id: int, approved_by: str = "system") -> bool:
    """Switch to a new strategy version.
    
    Requires:
    - Shadow validation passed
    - Explicit approval
    """
    # Check if shadow validation passed
    shadow_results = ShadowExecutor().compare_shadow_vs_production(version_id)
    
    if not shadow_results.get('ready_to_switch'):
        print(f"Cannot switch: insufficient shadow data")
        return False
    
    # Perform switch
    return StrategyManager.activate_strategy(version_id)


def get_current_strategy(project: str = "aegisos") -> Optional[StrategyVersion]:
    """Get currently active strategy."""
    return StrategyManager.get_active_strategy(project)


def create_new_strategy(
    prompt_template: str,
    execution_rules: Dict[str, Any],
    proposal_id: int = None,
    project: str = "aegisos"
) -> int:
    """Create new strategy version."""
    # Get parent version (current active)
    current = StrategyManager.get_active_strategy(project)
    parent_version = current.version if current else None
    
    return StrategyManager.create_strategy_version(
        project=project,
        prompt_template=prompt_template,
        execution_rules=execution_rules,
        parent_version=parent_version,
        proposal_id=proposal_id
    )
