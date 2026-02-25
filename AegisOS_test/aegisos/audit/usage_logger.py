"""Usage Logger - Phase5 Cost Audit Integration.

Design Principle:
- kimi_client is PURE - it never writes to database
- This module handles all usage logging for cost auditing
- Single source of truth for AI cost attribution

Usage:
    from aegisos.audit.usage_logger import log_inference_usage
    
    result = run_inference(request)
    if result.success:
        log_inference_usage(
            task_id=result.task_id,
            model=request.model,
            usage=result.usage,
            latency_ms=result.latency_ms,
            metadata=request.metadata
        )
"""
import os
import sys
from typing import Dict, Any, Optional
from datetime import datetime

# Add parent to path for imports
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.ai.ledger import log_ai_usage


def log_inference_usage(
    task_id: str,
    model: str,
    usage: Dict[str, int],
    latency_ms: int,
    metadata: Optional[Dict[str, Any]] = None,
    status: str = "committed"
) -> None:
    """Log inference usage to Phase5 ledger.
    
    This is the ONLY function that writes AI usage to database.
    Called by Executor after successful inference.
    
    Args:
        task_id: Task identifier
        model: Model name (e.g., "kimi-k2.5")
        usage: Dict with prompt_tokens, completion_tokens, total_tokens
        latency_ms: Response latency in milliseconds
        metadata: Additional context (requested_by, phase, etc.)
        status: "committed", "rejected", or "failed"
    
    Note:
        This function is idempotent - safe to call multiple times
        with same task_id (will update existing record).
    """
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
    
    # Calculate estimated cost (rough approximation)
    # Moonshot pricing: ~$0.003 per 1K tokens (varies by model)
    estimated_cost = (total_tokens / 1000) * 0.003
    
    # Serialize metadata for storage
    metadata_str = ""
    if metadata:
        try:
            import json
            metadata_str = json.dumps(metadata, ensure_ascii=False)
        except:
            metadata_str = str(metadata)
    
    # Write to ledger (convert task_id to int if needed)
    try:
        task_id_int = int(task_id)
    except (ValueError, TypeError):
        task_id_int = 0  # Fallback for non-numeric task IDs
    
    # Call ledger function (latency and metadata are not stored in current schema)
    # These fields are logged to stdout for now
    if metadata_str:
        print(f"[UsageLogger] task_id={task_id}, latency={latency_ms}ms, metadata={metadata_str[:100]}")
    
    log_ai_usage(
        task_id=task_id_int,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        status=status
    )


def log_inference_rejection(
    task_id: str,
    model: str,
    reason: str,
    estimated_tokens: int = 0
) -> None:
    """Log rejected inference (budget guard or validation failure).
    
    Args:
        task_id: Task identifier
        model: Model that would have been used
        reason: Rejection reason
        estimated_tokens: Estimated tokens that would have been used
    """
    log_inference_usage(
        task_id=task_id,
        model=model,
        usage={
            "prompt_tokens": estimated_tokens,
            "completion_tokens": 0,
            "total_tokens": estimated_tokens
        },
        latency_ms=0,
        metadata={"rejection_reason": reason},
        status="rejected"
    )


def log_inference_failure(
    task_id: str,
    model: str,
    error: str,
    prompt_tokens: int = 0
) -> None:
    """Log failed inference.
    
    Args:
        task_id: Task identifier
        model: Model that was attempted
        error: Error message
        prompt_tokens: Tokens sent (if known)
    """
    log_inference_usage(
        task_id=task_id,
        model=model,
        usage={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 0,
            "total_tokens": prompt_tokens
        },
        latency_ms=0,
        metadata={"error": error},
        status="failed"
    )


def get_usage_summary(hours: int = 24) -> Dict[str, Any]:
    """Get usage summary for reporting.
    
    Args:
        hours: Time window in hours
    
    Returns:
        Summary dict with totals and breakdowns
    """
    import sqlite3
    from pathlib import Path
    
    db_path = Path(_project_root) / "aegisos.db"
    
    if not db_path.exists():
        return {"error": "Database not found"}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get summary for time window
    cursor.execute("""
        SELECT 
            COUNT(*) as total_calls,
            SUM(total_tokens) as total_tokens,
            SUM(estimated_cost) as total_cost,
            SUM(CASE WHEN status='committed' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
        FROM ai_ledger
        WHERE created_at > unixepoch() - ?
    """, (hours * 3600,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "period_hours": hours,
            "total_calls": row[0] or 0,
            "total_tokens": row[1] or 0,
            "total_cost_usd": round(row[2] or 0, 4),
            "successful": row[3] or 0,
            "rejected": row[4] or 0,
            "failed": row[5] or 0
        }
    
    return {"period_hours": hours, "total_calls": 0}


# Backward compatibility
def write_ai_ledger_entry(*args, **kwargs):
    """Backward compatibility wrapper."""
    return log_inference_usage(*args, **kwargs)
