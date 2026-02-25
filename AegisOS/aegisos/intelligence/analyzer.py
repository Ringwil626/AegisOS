"""Analyzer - Behavior Observer for Phase6 Governed Optimization.

Analyzer scans usage_ledger and tasks to extract key metrics:
- Success rate trends
- Token consumption anomalies
- Retry rates
- Latency distribution

Design Principles:
- Read-only access to data
- No state modification
- Conservative thresholds
- Clear metric definitions
"""
import os
import sys
import sqlite3
import statistics
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import DB_PATH


@dataclass
class AnalysisMetrics:
    """Key metrics extracted from task execution data."""
    # Task counts
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    
    # Success metrics
    success_rate: float  # 0.0 - 1.0
    
    # Token metrics
    avg_tokens_per_task: float
    median_tokens_per_task: float
    max_tokens_per_task: int
    token_trend: str  # 'increasing', 'decreasing', 'stable'
    
    # Retry metrics
    retry_ratio: float  # 0.0 - 1.0
    
    # Latency metrics (ms)
    avg_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    latency_trend: str
    
    # Cost metrics
    avg_cost_per_task: float
    total_cost: float
    cost_trend: str
    
    # Time window
    window_hours: int
    from_time: int
    to_time: int


class BehaviorAnalyzer:
    """Analyzes system behavior from usage and task data."""
    
    def __init__(self, project: str = "aegisos"):
        self.project = project
    
    def analyze(self, window_hours: int = 24) -> Optional[AnalysisMetrics]:
        """Analyze recent task execution data.
        
        Args:
            window_hours: Time window for analysis
            
        Returns:
            AnalysisMetrics or None if insufficient data
        """
        from_time = int((datetime.now() - timedelta(hours=window_hours)).timestamp())
        to_time = int(datetime.now().timestamp())
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get task statistics (tasks table doesn't have project column yet)
        cursor.execute(
            """SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM tasks
            WHERE created_at >= ?
            AND created_at <= ?""",
            (from_time, to_time)
        )
        
        row = cursor.fetchone()
        total_tasks = row[0] or 0
        completed_tasks = row[1] or 0
        failed_tasks = row[2] or 0
        
        if total_tasks == 0:
            conn.close()
            return None
        
        # Calculate success rate
        success_rate = completed_tasks / total_tasks if total_tasks > 0 else 0
        
        # Get usage statistics from usage_ledger
        cursor.execute(
            """SELECT 
                tokens_total,
                latency_ms,
                cost_estimate
            FROM usage_ledger
            WHERE project = ?
            AND created_at >= ?
            AND created_at <= ?""",
            (self.project, from_time, to_time)
        )
        
        usage_rows = cursor.fetchall()
        
        # Token metrics
        tokens_list = [r[0] for r in usage_rows if r[0]]
        avg_tokens = statistics.mean(tokens_list) if tokens_list else 0
        median_tokens = statistics.median(tokens_list) if tokens_list else 0
        max_tokens = max(tokens_list) if tokens_list else 0
        
        # Latency metrics
        latency_list = [r[1] for r in usage_rows if r[1]]
        avg_latency = statistics.mean(latency_list) if latency_list else 0
        p50_latency = statistics.median(latency_list) if latency_list else 0
        p95_latency = self._percentile(latency_list, 95) if latency_list else 0
        p99_latency = self._percentile(latency_list, 99) if len(latency_list) > 10 else p95_latency
        
        # Cost metrics
        cost_list = [r[2] for r in usage_rows if r[2]]
        avg_cost = statistics.mean(cost_list) if cost_list else 0
        total_cost = sum(cost_list)
        
        # Calculate retry ratio from execution_log
        cursor.execute(
            """SELECT 
                COUNT(DISTINCT task_id) as unique_tasks,
                COUNT(*) as total_executions
            FROM execution_log
            WHERE task_id IN (
                SELECT id FROM tasks 
                WHERE project = ? 
                AND created_at >= ?
            )""",
            (self.project, from_time)
        )
        
        retry_row = cursor.fetchone()
        unique_tasks = retry_row[0] or 0
        total_executions = retry_row[1] or 0
        retry_ratio = (total_executions - unique_tasks) / unique_tasks if unique_tasks > 0 else 0
        
        conn.close()
        
        # Calculate trends (compare with previous window)
        token_trend = self._calculate_trend('tokens_total', window_hours)
        latency_trend = self._calculate_trend('latency_ms', window_hours)
        cost_trend = self._calculate_trend('cost_estimate', window_hours)
        
        return AnalysisMetrics(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            success_rate=success_rate,
            avg_tokens_per_task=avg_tokens,
            median_tokens_per_task=median_tokens,
            max_tokens_per_task=max_tokens,
            token_trend=token_trend,
            retry_ratio=retry_ratio,
            avg_latency=avg_latency,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            latency_trend=latency_trend,
            avg_cost_per_task=avg_cost,
            total_cost=total_cost,
            cost_trend=cost_trend,
            window_hours=window_hours,
            from_time=from_time,
            to_time=to_time
        )
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _calculate_trend(self, metric: str, window_hours: int) -> str:
        """Calculate trend by comparing current vs previous window."""
        now = int(datetime.now().timestamp())
        current_start = now - (window_hours * 3600)
        previous_start = current_start - (window_hours * 3600)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Current window average
        cursor.execute(
            f"""SELECT AVG({metric}) FROM usage_ledger
            WHERE project = ? AND created_at >= ?""",
            (self.project, current_start)
        )
        current_avg = cursor.fetchone()[0] or 0
        
        # Previous window average
        cursor.execute(
            f"""SELECT AVG({metric}) FROM usage_ledger
            WHERE project = ? AND created_at >= ? AND created_at < ?""",
            (self.project, previous_start, current_start)
        )
        previous_avg = cursor.fetchone()[0] or 0
        
        conn.close()
        
        if previous_avg == 0:
            return 'stable'
        
        change_pct = (current_avg - previous_avg) / previous_avg
        
        if change_pct > 0.1:
            return 'increasing'
        elif change_pct < -0.1:
            return 'decreasing'
        else:
            return 'stable'
    
    def detect_anomalies(self, metrics: AnalysisMetrics) -> List[Dict[str, Any]]:
        """Detect anomalies in metrics.
        
        Returns:
            List of anomaly descriptions
        """
        anomalies = []
        
        # Success rate drop
        if metrics.success_rate < 0.8:
            anomalies.append({
                'type': 'low_success_rate',
                'severity': 'high',
                'value': metrics.success_rate,
                'threshold': 0.8,
                'description': f'Success rate {metrics.success_rate:.1%} below threshold'
            })
        
        # Token inflation
        if metrics.token_trend == 'increasing':
            anomalies.append({
                'type': 'token_inflation',
                'severity': 'medium',
                'value': metrics.avg_tokens_per_task,
                'description': f'Token usage increasing, avg: {metrics.avg_tokens_per_task:.0f}'
            })
        
        # High retry ratio
        if metrics.retry_ratio > 0.2:
            anomalies.append({
                'type': 'high_retry_rate',
                'severity': 'medium',
                'value': metrics.retry_ratio,
                'threshold': 0.2,
                'description': f'Retry ratio {metrics.retry_ratio:.1%} above threshold'
            })
        
        # Latency spike
        if metrics.latency_trend == 'increasing':
            anomalies.append({
                'type': 'latency_increase',
                'severity': 'medium',
                'value': metrics.p95_latency,
                'description': f'P95 latency increasing: {metrics.p95_latency:.0f}ms'
            })
        
        # Cost spike
        if metrics.cost_trend == 'increasing':
            anomalies.append({
                'type': 'cost_increase',
                'severity': 'low',
                'value': metrics.avg_cost_per_task,
                'description': f'Cost per task increasing: ${metrics.avg_cost_per_task:.4f}'
            })
        
        return anomalies


def analyze_project(project: str = "aegisos", window_hours: int = 24) -> Optional[AnalysisMetrics]:
    """Convenience function to analyze a project."""
    analyzer = BehaviorAnalyzer(project=project)
    return analyzer.analyze(window_hours=window_hours)


def format_metrics(metrics: AnalysisMetrics) -> str:
    """Format metrics for display."""
    lines = [
        f"Analysis for {metrics.window_hours}h window:",
        f"  Tasks: {metrics.completed_tasks}/{metrics.total_tasks} succeeded ({metrics.success_rate:.1%})",
        f"  Tokens: avg={metrics.avg_tokens_per_task:.0f}, median={metrics.median_tokens_per_task:.0f}, max={metrics.max_tokens_per_task}",
        f"  Token trend: {metrics.token_trend}",
        f"  Retry ratio: {metrics.retry_ratio:.1%}",
        f"  Latency: avg={metrics.avg_latency:.0f}ms, p95={metrics.p95_latency:.0f}ms, p99={metrics.p99_latency:.0f}ms",
        f"  Latency trend: {metrics.latency_trend}",
        f"  Cost: avg=${metrics.avg_cost_per_task:.4f}, total=${metrics.total_cost:.4f}",
        f"  Cost trend: {metrics.cost_trend}"
    ]
    return "\n".join(lines)
