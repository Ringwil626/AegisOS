"""Optimizer - Generate Candidate Execution Strategies (Proposals Only).

Optimizer generates optimization proposals based on analysis.
It does NOT directly modify the system - it only creates proposals
for human approval.

Design Principles:
- Generate proposals, not changes
- Clear expected gain and risk assessment
- Versioned strategies
- No auto-execution
"""
import os
import sys
import json
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH
from aegisos.intelligence.analyzer import AnalysisMetrics


class ProposalType(Enum):
    """Types of optimization proposals."""
    PROMPT_TUNING = "prompt_tuning"
    TASK_SPLIT = "task_split"
    MODEL_SWITCH = "model_switch"
    CONTEXT_COMPRESSION = "context_compression"


class RiskLevel(Enum):
    """Risk levels for proposals."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProposalStatus(Enum):
    """Status of proposals."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SHADOW = "shadow"
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass
class Proposal:
    """Optimization proposal."""
    id: Optional[int]
    type: ProposalType
    project: str
    reason: str
    action: str
    expected_gain: str
    risk_level: RiskLevel
    status: ProposalStatus
    created_at: int
    approved_at: Optional[int]
    approved_by: Optional[str]


class ProposalManager:
    """Manages optimization proposals in database."""
    
    @staticmethod
    def init_tables():
        """Initialize proposals table."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                project TEXT NOT NULL,
                reason TEXT NOT NULL,
                action TEXT NOT NULL,
                expected_gain TEXT,
                risk_level TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at INTEGER DEFAULT (unixepoch()),
                approved_at INTEGER,
                approved_by TEXT,
                shadow_metrics TEXT,
                production_metrics TEXT
            )
        """)
        
        # Strategy versions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                project TEXT NOT NULL,
                prompt_template_hash TEXT,
                execution_rules TEXT,
                created_at INTEGER DEFAULT (unixepoch()),
                activated_at INTEGER,
                status TEXT DEFAULT 'pending',
                parent_version INTEGER,
                proposal_id INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_proposal(
        type: ProposalType,
        project: str,
        reason: str,
        action: str,
        expected_gain: str,
        risk_level: RiskLevel
    ) -> int:
        """Create a new optimization proposal.
        
        Returns:
            Proposal ID
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO proposals 
            (type, project, reason, action, expected_gain, risk_level, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (type.value, project, reason, action, expected_gain, risk_level.value))
        
        proposal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return proposal_id
    
    @staticmethod
    def get_proposal(proposal_id: int) -> Optional[Proposal]:
        """Get proposal by ID."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, type, project, reason, action, expected_gain,
                   risk_level, status, created_at, approved_at, approved_by
            FROM proposals
            WHERE id = ?
        """, (proposal_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Proposal(
            id=row[0],
            type=ProposalType(row[1]),
            project=row[2],
            reason=row[3],
            action=row[4],
            expected_gain=row[5],
            risk_level=RiskLevel(row[6]),
            status=ProposalStatus(row[7]),
            created_at=row[8],
            approved_at=row[9],
            approved_by=row[10]
        )
    
    @staticmethod
    def list_proposals(project: str = None, 
                      status: ProposalStatus = None,
                      limit: int = 10) -> List[Proposal]:
        """List proposals with optional filters."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        query = """
            SELECT id, type, project, reason, action, expected_gain,
                   risk_level, status, created_at, approved_at, approved_by
            FROM proposals
            WHERE 1=1
        """
        params = []
        
        if project:
            query += " AND project = ?"
            params.append(project)
        
        if status:
            query += " AND status = ?"
            params.append(status.value)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Proposal(
                id=row[0],
                type=ProposalType(row[1]),
                project=row[2],
                reason=row[3],
                action=row[4],
                expected_gain=row[5],
                risk_level=RiskLevel(row[6]),
                status=ProposalStatus(row[7]),
                created_at=row[8],
                approved_at=row[9],
                approved_by=row[10]
            )
            for row in rows
        ]
    
    @staticmethod
    def approve_proposal(proposal_id: int, approved_by: str) -> bool:
        """Approve a proposal."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET status = 'approved',
                approved_at = unixepoch(),
                approved_by = ?
            WHERE id = ? AND status = 'pending'
        """, (approved_by, proposal_id))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    @staticmethod
    def reject_proposal(proposal_id: int, reason: str = None) -> bool:
        """Reject a proposal."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET status = 'rejected'
            WHERE id = ? AND status = 'pending'
        """, (proposal_id,))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return success
    
    @staticmethod
    def update_shadow_metrics(proposal_id: int, metrics: Dict[str, Any]):
        """Update shadow execution metrics for a proposal."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE proposals
            SET shadow_metrics = ?,
                status = 'shadow'
            WHERE id = ?
        """, (json.dumps(metrics), proposal_id))
        
        conn.commit()
        conn.close()


class StrategyOptimizer:
    """Generates optimization proposals based on analysis."""
    
    def __init__(self, project: str = "aegisos"):
        self.project = project
        ProposalManager.init_tables()
    
    def generate_proposals(self, metrics: AnalysisMetrics, 
                          anomalies: List[Dict[str, Any]]) -> List[int]:
        """Generate optimization proposals.
        
        Returns:
            List of created proposal IDs
        """
        proposal_ids = []
        
        # Analyze anomalies and generate appropriate proposals
        anomaly_types = {a['type'] for a in anomalies}
        
        # Token inflation / Cost increase → Prompt tuning
        if 'token_inflation' in anomaly_types or 'cost_increase' in anomaly_types:
            proposal_id = self._propose_prompt_tuning(metrics)
            if proposal_id:
                proposal_ids.append(proposal_id)
        
        # Latency increase → Task split
        if 'latency_increase' in anomaly_types:
            proposal_id = self._propose_task_split(metrics)
            if proposal_id:
                proposal_ids.append(proposal_id)
        
        # Low success rate → Model switch
        if 'low_success_rate' in anomaly_types:
            proposal_id = self._propose_model_switch(metrics)
            if proposal_id:
                proposal_ids.append(proposal_id)
        
        # High retry rate → Context optimization
        if 'high_retry_rate' in anomaly_types:
            proposal_id = self._propose_context_compression(metrics)
            if proposal_id:
                proposal_ids.append(proposal_id)
        
        return proposal_ids
    
    def _propose_prompt_tuning(self, metrics: AnalysisMetrics) -> Optional[int]:
        """Generate prompt tuning proposal."""
        return ProposalManager.create_proposal(
            type=ProposalType.PROMPT_TUNING,
            project=self.project,
            reason=f"Token usage trending up (avg {metrics.avg_tokens_per_task:.0f} tokens)",
            action="Optimize prompt templates to reduce token consumption",
            expected_gain=f"Reduce token usage by 15-20% (save ~${metrics.avg_cost_per_task * 0.15:.4f} per task)",
            risk_level=RiskLevel.LOW
        )
    
    def _propose_task_split(self, metrics: AnalysisMetrics) -> Optional[int]:
        """Generate task split proposal."""
        return ProposalManager.create_proposal(
            type=ProposalType.TASK_SPLIT,
            project=self.project,
            reason=f"P95 latency high ({metrics.p95_latency:.0f}ms)",
            action="Break large tasks into smaller chunks for parallel execution",
            expected_gain=f"Reduce P95 latency by 30-40% (from {metrics.p95_latency:.0f}ms to ~{metrics.p95_latency * 0.7:.0f}ms)",
            risk_level=RiskLevel.MEDIUM
        )
    
    def _propose_model_switch(self, metrics: AnalysisMetrics) -> Optional[int]:
        """Generate model switch proposal."""
        return ProposalManager.create_proposal(
            type=ProposalType.MODEL_SWITCH,
            project=self.project,
            reason=f"Low success rate ({metrics.success_rate:.1%})",
            action="Evaluate switching to more capable model for complex tasks",
            expected_gain=f"Improve success rate from {metrics.success_rate:.1%} to ~90%",
            risk_level=RiskLevel.HIGH
        )
    
    def _propose_context_compression(self, metrics: AnalysisMetrics) -> Optional[int]:
        """Generate context compression proposal."""
        return ProposalManager.create_proposal(
            type=ProposalType.CONTEXT_COMPRESSION,
            project=self.project,
            reason=f"High retry ratio ({metrics.retry_ratio:.1%})",
            action="Compress context to reduce confusion and retries",
            expected_gain=f"Reduce retry ratio from {metrics.retry_ratio:.1%} to <10%",
            risk_level=RiskLevel.MEDIUM
        )


def create_proposal(
    type: str,
    reason: str,
    action: str,
    expected_gain: str,
    risk_level: str = "medium",
    project: str = "aegisos"
) -> int:
    """Convenience function to create a proposal."""
    return ProposalManager.create_proposal(
        type=ProposalType(type),
        project=project,
        reason=reason,
        action=action,
        expected_gain=expected_gain,
        risk_level=RiskLevel(risk_level)
    )


def list_pending_proposals(project: str = None) -> List[Proposal]:
    """Convenience function to list pending proposals."""
    return ProposalManager.list_proposals(project=project, status=ProposalStatus.PENDING)


def approve_proposal(proposal_id: int, approved_by: str = "system") -> bool:
    """Convenience function to approve a proposal."""
    return ProposalManager.approve_proposal(proposal_id, approved_by)
