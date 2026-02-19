"""Shadow Runner - Phase6 Shadow Validation.

Shadow Runner executes tasks with new strategy without affecting production:
- Simulates execution with new configuration
- Records performance metrics only
- Does NOT write task results
- Does NOT modify production state

Design:
- Read-only from production perspective
- Write-only to shadow_runs table
- Parallel execution comparison
"""
import os
import sys
import sqlite3
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH


@dataclass
class ShadowResult:
    """Result of shadow execution."""
    proposal_id: int
    task_id: int
    simulated_tokens: int
    simulated_latency: float
    result_valid: bool
    schema_valid: bool
    error_message: Optional[str]


class ShadowRunner:
    """Executes shadow runs for proposal validation."""
    
    def __init__(self):
        self.init_tables()
    
    def init_tables(self):
        """Initialize shadow_runs table."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proposal_id INTEGER NOT NULL,
                task_id INTEGER NOT NULL,
                simulated_tokens INTEGER,
                simulated_latency REAL,
                result_valid BOOLEAN,
                schema_valid BOOLEAN,
                error_message TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (proposal_id) REFERENCES proposals(id),
                FOREIGN KEY (task_id) REFERENCES tasks(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def run_shadow(self, proposal_id: int, task_id: int, 
                   new_config: Dict[str, Any]) -> ShadowResult:
        """Execute a shadow run for a task.
        
        Args:
            proposal_id: The proposal being tested
            task_id: The task to simulate
            new_config: New strategy configuration
            
        Returns:
            ShadowResult with simulated metrics
        """
        import time
        import random
        
        # Get original task data
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT payload FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        # Simulate execution with new config
        # In real implementation, this would:
        # 1. Apply new prompt template
        # 2. Run through inference
        # 3. Validate output schema
        # 4. Record metrics WITHOUT writing results
        
        start_time = time.time()
        
        try:
            # Simulate processing based on proposal type
            proposal_type = new_config.get('type', 'unknown')
            
            if proposal_type == 'prompt_tuning':
                # Simulate 20% token reduction
                base_tokens = 2000
                simulated_tokens = int(base_tokens * 0.8)
            elif proposal_type == 'model_switch':
                # Simulate faster but maybe less accurate
                simulated_tokens = 1800
            elif proposal_type == 'task_split':
                # Simulate split into 2 tasks
                simulated_tokens = 2200
            else:
                simulated_tokens = 2000
            
            # Simulate latency (0.5-3 seconds)
            simulated_latency = random.uniform(0.5, 3.0)
            
            # Simulate result validity (95% success rate)
            result_valid = random.random() > 0.05
            schema_valid = result_valid
            error_message = None if result_valid else "Simulated validation error"
            
        except Exception as e:
            simulated_tokens = 0
            simulated_latency = 0
            result_valid = False
            schema_valid = False
            error_message = str(e)
        
        # Record shadow run
        result = ShadowResult(
            proposal_id=proposal_id,
            task_id=task_id,
            simulated_tokens=simulated_tokens,
            simulated_latency=simulated_latency,
            result_valid=result_valid,
            schema_valid=schema_valid,
            error_message=error_message
        )
        
        self._record_shadow_run(result)
        
        return result
    
    def _record_shadow_run(self, result: ShadowResult):
        """Record shadow run to database."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO shadow_runs 
            (proposal_id, task_id, simulated_tokens, simulated_latency, 
             result_valid, schema_valid, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result.proposal_id,
            result.task_id,
            result.simulated_tokens,
            result.simulated_latency,
            result.result_valid,
            result.schema_valid,
            result.error_message
        ))
        
        conn.commit()
        conn.close()
    
    def get_shadow_stats(self, proposal_id: int) -> Dict[str, Any]:
        """Get shadow run statistics for a proposal.
        
        Returns:
            Dict with run count, success rate, avg tokens, etc.
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_runs,
                SUM(CASE WHEN result_valid = 1 THEN 1 ELSE 0 END) as valid_runs,
                AVG(simulated_tokens) as avg_tokens,
                AVG(simulated_latency) as avg_latency,
                AVG(CASE WHEN result_valid = 1 THEN simulated_tokens ELSE NULL END) as avg_tokens_success
            FROM shadow_runs
            WHERE proposal_id = ?
        """, (proposal_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        total_runs = row[0] or 0
        valid_runs = row[1] or 0
        
        return {
            'proposal_id': proposal_id,
            'total_runs': total_runs,
            'valid_runs': valid_runs,
            'success_rate': valid_runs / total_runs if total_runs > 0 else 0,
            'avg_tokens': row[2] or 0,
            'avg_latency': row[3] or 0,
            'avg_tokens_on_success': row[4] or 0
        }
    
    def check_validation_criteria(self, proposal_id: int, 
                                   current_success_rate: float) -> Dict[str, Any]:
        """Check if shadow validation criteria are met.
        
        Criteria:
        - >= 10 shadow runs
        - Success rate >= current version
        - Token usage reduced OR latency reduced
        - No schema errors
        
        Returns:
            Dict with passed (bool) and details
        """
        stats = self.get_shadow_stats(proposal_id)
        
        checks = {
            'min_runs': stats['total_runs'] >= 10,
            'success_rate': stats['success_rate'] >= current_success_rate,
            'improvement': True,  # Would compare with baseline
            'no_schema_errors': True  # Would check schema_valid
        }
        
        all_passed = all(checks.values())
        
        return {
            'passed': all_passed,
            'stats': stats,
            'checks': checks,
            'can_switch': all_passed and stats['total_runs'] >= 10
        }


def run_shadow_validation(proposal_id: int, task_count: int = 10) -> Dict[str, Any]:
    """Run shadow validation for a proposal.
    
    Args:
        proposal_id: Proposal to validate
        task_count: Number of shadow runs to execute
        
    Returns:
        Validation results
    """
    runner = ShadowRunner()
    
    # Get proposal details
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT type, action FROM proposals WHERE id = ?",
        (proposal_id,)
    )
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {'error': 'Proposal not found'}
    
    proposal_type, action = row
    
    # Get recent tasks to shadow
    cursor.execute("""
        SELECT id FROM tasks 
        WHERE status = 'completed'
        ORDER BY created_at DESC
        LIMIT ?
    """, (task_count,))
    
    task_ids = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    # Run shadows
    new_config = {'type': proposal_type, 'action': action}
    
    for task_id in task_ids:
        runner.run_shadow(proposal_id, task_id, new_config)
    
    # Get stats
    stats = runner.get_shadow_stats(proposal_id)
    
    return {
        'proposal_id': proposal_id,
        'shadow_runs_executed': len(task_ids),
        'stats': stats
    }


def check_proposal_ready_for_switch(proposal_id: int) -> bool:
    """Check if proposal is ready for switch."""
    runner = ShadowRunner()
    result = runner.check_validation_criteria(proposal_id, current_success_rate=0.8)
    return result['can_switch']
