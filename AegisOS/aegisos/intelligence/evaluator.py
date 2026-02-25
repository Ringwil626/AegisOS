"""Evaluator - Decide if Optimization is Warranted.

Evaluator checks if detected anomalies meet the threshold for
optimization, based on policy.yaml configuration.

Design Principles:
- Conservative by default (better to under-optimize)
- Prevent "overfitting-style random changes"
- Clear go/no-go decision
"""
import os
import sys
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.intelligence.analyzer import AnalysisMetrics


class OptimizationDecision(Enum):
    """Decision outcomes for optimization."""
    PROCEED = "proceed"           # Generate proposal
    WAIT = "wait"                 # Wait for more data
    SKIP = "skip"                 # Skip this cycle
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class EvaluationResult:
    """Result of optimization evaluation."""
    decision: OptimizationDecision
    reasons: List[str]
    triggered_thresholds: List[str]
    confidence: float  # 0.0 - 1.0
    recommendation: Optional[str] = None


class PolicyLoader:
    """Load and cache optimization policy."""
    
    _policy_cache: Optional[Dict] = None
    
    @classmethod
    def load_policy(cls, force_reload: bool = False) -> Dict[str, Any]:
        """Load policy from YAML file."""
        if cls._policy_cache is not None and not force_reload:
            return cls._policy_cache
        
        policy_path = os.path.join(_current_dir, "policy.yaml")
        
        if os.path.exists(policy_path):
            try:
                import yaml
                with open(policy_path, 'r', encoding='utf-8') as f:
                    cls._policy_cache = yaml.safe_load(f) or {}
            except ImportError:
                # YAML not available, use default
                cls._policy_cache = cls._default_policy()
        else:
            # Default policy
            cls._policy_cache = cls._default_policy()
        
        return cls._policy_cache
    
    @classmethod
    def _default_policy(cls) -> Dict[str, Any]:
        """Default policy when YAML not available."""
        return {
            'analysis': {'min_task_count': 10},
            'optimize_when': {
                'success_rate_drop': 15,
                'avg_tokens_increase': 25,
                'retry_ratio': 20,
                'p95_latency_increase': 30,
                'cost_per_task_increase': 20
            },
            'proposals': {'max_pending': 5}
        }


class OptimizationEvaluator:
    """Evaluates whether optimization should proceed."""
    
    def __init__(self, project: str = "aegisos"):
        self.project = project
        self.policy = PolicyLoader.load_policy()
    
    def evaluate(self, metrics: AnalysisMetrics, 
                 anomalies: List[Dict[str, Any]]) -> EvaluationResult:
        """Evaluate if optimization is warranted.
        
        Args:
            metrics: Analysis metrics
            anomalies: Detected anomalies
            
        Returns:
            EvaluationResult with decision
        """
        reasons = []
        triggered = []
        
        # Check minimum task count
        min_tasks = self.policy.get('analysis', {}).get('min_task_count', 10)
        if metrics.total_tasks < min_tasks:
            return EvaluationResult(
                decision=OptimizationDecision.INSUFFICIENT_DATA,
                reasons=[f"Insufficient tasks: {metrics.total_tasks} < {min_tasks}"],
                triggered_thresholds=[],
                confidence=0.0
            )
        
        # Get thresholds
        thresholds = self.policy.get('optimize_when', {})
        
        # Check success rate drop
        success_threshold = thresholds.get('success_rate_drop', 15)
        if metrics.success_rate < (1 - success_threshold / 100):
            triggered.append(f"success_rate_drop ({metrics.success_rate:.1%})")
            reasons.append(f"Success rate {metrics.success_rate:.1%} below threshold")
        
        # Check token increase
        token_threshold = thresholds.get('avg_tokens_increase', 25)
        if metrics.token_trend == 'increasing':
            triggered.append(f"avg_tokens_increase")
            reasons.append(f"Token usage trending up ({metrics.avg_tokens_per_task:.0f} avg)")
        
        # Check retry ratio
        retry_threshold = thresholds.get('retry_ratio', 20)
        if metrics.retry_ratio > (retry_threshold / 100):
            triggered.append(f"retry_ratio ({metrics.retry_ratio:.1%})")
            reasons.append(f"Retry ratio {metrics.retry_ratio:.1%} exceeds {retry_threshold}%")
        
        # Check latency increase
        latency_threshold = thresholds.get('p95_latency_increase', 30)
        if metrics.latency_trend == 'increasing':
            triggered.append(f"p95_latency_increase")
            reasons.append(f"P95 latency trending up ({metrics.p95_latency:.0f}ms)")
        
        # Check cost increase
        cost_threshold = thresholds.get('cost_per_task_increase', 20)
        if metrics.cost_trend == 'increasing':
            triggered.append(f"cost_per_task_increase")
            reasons.append(f"Cost per task trending up (${metrics.avg_cost_per_task:.4f})")
        
        # High severity anomalies always trigger evaluation
        high_severity = [a for a in anomalies if a.get('severity') == 'high']
        if high_severity:
            triggered.append("high_severity_anomalies")
            reasons.append(f"{len(high_severity)} high severity anomalies detected")
        
        # Make decision
        if triggered:
            # Check if we have too many pending proposals
            pending_count = self._count_pending_proposals()
            max_pending = self.policy.get('proposals', {}).get('max_pending', 5)
            
            if pending_count >= max_pending:
                return EvaluationResult(
                    decision=OptimizationDecision.WAIT,
                    reasons=[f"Too many pending proposals ({pending_count}/{max_pending})"],
                    triggered_thresholds=triggered,
                    confidence=0.5
                )
            
            confidence = min(0.9, 0.5 + (len(triggered) * 0.1))
            
            return EvaluationResult(
                decision=OptimizationDecision.PROCEED,
                reasons=reasons,
                triggered_thresholds=triggered,
                confidence=confidence,
                recommendation=self._generate_recommendation(metrics, anomalies)
            )
        
        return EvaluationResult(
            decision=OptimizationDecision.SKIP,
            reasons=["No thresholds triggered"],
            triggered_thresholds=[],
            confidence=0.0
        )
    
    def _count_pending_proposals(self) -> int:
        """Count pending proposals in database."""
        import sqlite3
        from aegisos.db.sqlite_store import DB_PATH
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if proposals table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='proposals'"
        )
        if not cursor.fetchone():
            conn.close()
            return 0
        
        cursor.execute(
            "SELECT COUNT(*) FROM proposals WHERE status = 'pending'"
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def _generate_recommendation(self, metrics: AnalysisMetrics, 
                                  anomalies: List[Dict[str, Any]]) -> str:
        """Generate optimization recommendation based on metrics."""
        recommendations = []
        
        # Check anomaly types
        anomaly_types = [a['type'] for a in anomalies]
        
        if 'token_inflation' in anomaly_types or 'cost_increase' in anomaly_types:
            recommendations.append("prompt_tuning")
        
        if 'latency_increase' in anomaly_types:
            recommendations.append("task_split")
        
        if 'high_retry_rate' in anomaly_types:
            recommendations.append("prompt_tuning")
        
        if 'low_success_rate' in anomaly_types:
            recommendations.append("model_switch")
        
        if not recommendations:
            recommendations.append("general_review")
        
        return ", ".join(recommendations)


def evaluate_optimization(metrics: AnalysisMetrics, 
                         anomalies: List[Dict[str, Any]],
                         project: str = "aegisos") -> EvaluationResult:
    """Convenience function to evaluate optimization need."""
    evaluator = OptimizationEvaluator(project=project)
    return evaluator.evaluate(metrics, anomalies)


def format_evaluation(result: EvaluationResult) -> str:
    """Format evaluation result for display."""
    lines = [
        f"Decision: {result.decision.value}",
        f"Confidence: {result.confidence:.0%}"
    ]
    
    if result.triggered_thresholds:
        lines.append(f"Triggered: {', '.join(result.triggered_thresholds)}")
    
    if result.reasons:
        lines.append("Reasons:")
        for reason in result.reasons:
            lines.append(f"  - {reason}")
    
    if result.recommendation:
        lines.append(f"Recommended: {result.recommendation}")
    
    return "\n".join(lines)
