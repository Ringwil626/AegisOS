"""Retrieval - Phase 7: Persistent Intelligence Layer.

Retrieves relevant engineering memories before AI evolution.
Provides historical context for decision-making.
"""
import json
import sys
import os

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.memory.vector_index import get_vector_index, refresh_index
from aegisos.db.sqlite_store import get_all_memories


def retrieve_similar_cases(goal: str, top_k: int = 5) -> dict:
    """Retrieve similar past evolution cases.
    
    Called BEFORE any evolve request.
    Provides AI with historical context.
    
    Args:
        goal: Evolution goal description
        top_k: Number of similar cases to retrieve
    
    Returns:
        Dictionary with historical_successes and historical_failures
    """
    index = get_vector_index()
    
    # Search for similar memories
    similar = index.search_similar(goal, top_k=top_k * 2)  # Get more for filtering
    
    successes = []
    failures = []
    
    # Get all memories for lookup
    all_memories = {m[0]: m for m in get_all_memories(limit=1000)}
    
    for memory_id, similarity in similar:
        if memory_id not in all_memories:
            continue
        
        memory = all_memories[memory_id]
        outcome = memory[4]  # outcome column
        
        case = {
            "memory_id": memory_id,
            "similarity": round(similarity, 3),
            "context": memory[2],
            "change_summary": memory[3],
            "outcome": outcome,
            "metrics": json.loads(memory[5]) if memory[5] else {}
        }
        
        if outcome == "success":
            successes.append(case)
        elif outcome in ["rollback", "degraded"]:
            failures.append(case)
    
    # Limit results
    successes = successes[:top_k]
    failures = failures[:top_k]
    
    return {
        "historical_successes": successes,
        "historical_failures": failures,
        "total_cases_found": len(successes) + len(failures)
    }


def compute_risk_forecast(goal: str) -> dict:
    """Compute risk forecast for evolution goal.
    
    Analyzes similar past cases to estimate failure probability.
    
    Returns:
        {
            "risk_level": "low" / "medium" / "high" / "critical",
            "failure_rate": float (0.0 to 1.0),
            "similar_cases_count": int,
            "recommendation": str
        }
    """
    cases = retrieve_similar_cases(goal, top_k=10)
    
    successes = len(cases["historical_successes"])
    failures = len(cases["historical_failures"])
    total = successes + failures
    
    if total == 0:
        return {
            "risk_level": "unknown",
            "failure_rate": 0.0,
            "similar_cases_count": 0,
            "recommendation": "No historical data. Proceed with caution."
        }
    
    failure_rate = failures / total
    
    # Determine risk level
    if failure_rate >= 0.7:
        risk_level = "critical"
        recommendation = "High failure rate detected. Manual review required."
    elif failure_rate >= 0.4:
        risk_level = "high"
        recommendation = "Mixed history. Consider alternative approaches."
    elif failure_rate >= 0.2:
        risk_level = "medium"
        recommendation = "Some risk. Proceed with monitoring."
    else:
        risk_level = "low"
        recommendation = "Good historical success rate. Safe to proceed."
    
    return {
        "risk_level": risk_level,
        "failure_rate": round(failure_rate, 2),
        "similar_cases_count": total,
        "recommendation": recommendation
    }


def format_retrieval_context(retrieval_result: dict) -> str:
    """Format retrieval result as context string for AI.
    
    This is what the AI receives before generating proposal.
    """
    lines = []
    
    lines.append("=== HISTORICAL ENGINEERING CONTEXT ===")
    lines.append("")
    
    successes = retrieval_result.get("historical_successes", [])
    failures = retrieval_result.get("historical_failures", [])
    
    if successes:
        lines.append(f"Historical Successes ({len(successes)}):")
        for i, case in enumerate(successes, 1):
            lines.append(f"  {i}. {case['context']}")
            lines.append(f"     Change: {case['change_summary']}")
            lines.append(f"     Similarity: {case['similarity']}")
            lines.append("")
    
    if failures:
        lines.append(f"Historical Failures ({len(failures)}):")
        for i, case in enumerate(failures, 1):
            lines.append(f"  {i}. {case['context']}")
            lines.append(f"     Change: {case['change_summary']}")
            lines.append(f"     Outcome: {case['outcome']}")
            metrics = case.get("metrics", {})
            if metrics.get("rolled_back"):
                lines.append(f"     ⚠️ Was rolled back")
            lines.append("")
    
    if not successes and not failures:
        lines.append("No historical data available for this type of change.")
        lines.append("")
    
    lines.append("=== END HISTORICAL CONTEXT ===")
    
    return "\n".join(lines)


def get_evolution_context(goal: str) -> tuple:
    """Get complete context for evolution.
    
    Returns:
        (context_string, risk_forecast_dict)
    """
    retrieval = retrieve_similar_cases(goal)
    risk = compute_risk_forecast(goal)
    context = format_retrieval_context(retrieval)
    
    return context, risk
