"""Outcome Analyzer - Phase 7: Persistent Intelligence Layer.

Generates engineering memory from real system outcomes.
NOT from AI-generated summaries.

Sources:
    - Validator results
    - Runtime health signals
    - Rollback events
    - Cost delta from ai_ledger

AI is NOT allowed to write memory records.
Only system-generated outcomes are stored.
"""
import json
import sys
import os

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import (
    get_evolution_job,
    get_task_ledger_summary,
    create_memory_record
)


class OutcomeAnalyzer:
    """Analyzes evolution outcomes and generates system memory.
    
    This class collects factual data from multiple sources:
    - Validator pass/fail status
    - Runtime health after deployment
    - Rollback events
    - Cost changes
    
    It produces structured experience records WITHOUT AI involvement.
    """
    
    def __init__(self):
        self.analysis_results = {}
    
    def collect_validator_result(self, job_id: int, passed: bool, test_output: str = ""):
        """Record validator outcome."""
        self.analysis_results[job_id] = {
            "validator_passed": passed,
            "test_output": test_output[:500]  # Truncate for storage
        }
    
    def collect_runtime_health(self, job_id: int, health_status: str, 
                               supervisor_alive: bool, error_count: int = 0):
        """Record runtime health after deployment."""
        if job_id not in self.analysis_results:
            self.analysis_results[job_id] = {}
        
        self.analysis_results[job_id].update({
            "health_status": health_status,
            "supervisor_alive": supervisor_alive,
            "error_count": error_count
        })
    
    def collect_rollback_event(self, job_id: int, reason: str):
        """Record rollback event."""
        if job_id not in self.analysis_results:
            self.analysis_results[job_id] = {}
        
        self.analysis_results[job_id].update({
            "rolled_back": True,
            "rollback_reason": reason
        })
    
    def collect_cost_delta(self, job_id: int, task_id: int):
        """Collect cost information from ai_ledger."""
        ledger_summary = get_task_ledger_summary(task_id)
        
        if job_id not in self.analysis_results:
            self.analysis_results[job_id] = {}
        
        self.analysis_results[job_id].update({
            "total_tokens": ledger_summary.get("total_tokens", 0),
            "total_cost": ledger_summary.get("total_cost", 0),
            "ai_calls": ledger_summary.get("call_count", 0)
        })
    
    def determine_outcome(self, job_id: int) -> str:
        """Determine overall outcome from collected data.
        
        Returns:
            'success' - Everything worked well
            'rollback' - Had to roll back
            'degraded' - Working but with issues
        """
        data = self.analysis_results.get(job_id, {})
        
        # Rollback is definitive failure
        if data.get("rolled_back", False):
            return "rollback"
        
        # Validator failure
        if not data.get("validator_passed", True):
            return "rollback"
        
        # Health issues
        if data.get("health_status") == "unhealthy":
            return "degraded"
        
        if data.get("error_count", 0) > 0:
            return "degraded"
        
        # Supervisor not alive
        if not data.get("supervisor_alive", True):
            return "rollback"
        
        return "success"
    
    def generate_memory_record(self, job_id: int) -> dict:
        """Generate structured memory record from analysis.
        
        This is called AFTER the evolution deployment lifecycle ends.
        It produces factual summary WITHOUT using AI.
        """
        job = get_evolution_job(job_id)
        if not job:
            return None
        
        task_id = job[1]
        outcome = self.determine_outcome(job_id)
        data = self.analysis_results.get(job_id, {})
        
        # Build change summary from system facts
        changes = []
        if data.get("validator_passed"):
            changes.append("validation passed")
        if data.get("supervisor_alive"):
            changes.append("supervisor stable")
        if data.get("total_tokens", 0) > 0:
            changes.append(f"consumed {data['total_tokens']} tokens")
        
        change_summary = "; ".join(changes) if changes else "unknown changes"
        
        # Build metrics JSON
        metrics = {
            "validator_passed": data.get("validator_passed", False),
            "supervisor_alive": data.get("supervisor_alive", False),
            "error_count": data.get("error_count", 0),
            "total_tokens": data.get("total_tokens", 0),
            "total_cost": data.get("total_cost", 0),
            "ai_calls": data.get("ai_calls", 0),
            "rolled_back": data.get("rolled_back", False)
        }
        
        return {
            "evolution_job_id": job_id,
            "context": f"Evolution job {job_id} for task {task_id}",
            "change_summary": change_summary,
            "outcome": outcome,
            "metrics": json.dumps(metrics)
        }
    
    def save_memory(self, job_id: int) -> int:
        """Save memory record to database.
        
        Returns:
            Memory record ID
        """
        record = self.generate_memory_record(job_id)
        if not record:
            return None
        
        memory_id = create_memory_record(
            evolution_job_id=record["evolution_job_id"],
            context=record["context"],
            change_summary=record["change_summary"],
            outcome=record["outcome"],
            metrics=record["metrics"],
            embedding_id=None  # Will be set by vector index
        )
        
        print(f"[OutcomeAnalyzer] Memory record {memory_id} created for job {job_id}")
        print(f"[OutcomeAnalyzer] Outcome: {record['outcome']}")
        
        return memory_id


def auto_analyze_and_save(job_id: int):
    """Automatically analyze evolution job and save memory.
    
    This is called by the system after evolution lifecycle completes.
    No AI is involved in this process.
    """
    analyzer = OutcomeAnalyzer()
    
    # Get job details
    job = get_evolution_job(job_id)
    if not job:
        print(f"[OutcomeAnalyzer] Job {job_id} not found")
        return None
    
    task_id = job[1]
    
    # Collect all available data
    # In production, these would come from actual monitoring
    # For now, we infer from job status
    
    if job[3] == "validated":
        analyzer.collect_validator_result(job_id, True)
    elif job[3] == "rejected":
        analyzer.collect_validator_result(job_id, False)
    
    # Collect cost data
    analyzer.collect_cost_delta(job_id, task_id)
    
    # Infer from final status
    if job[3] in ["approved", "deployed"]:
        analyzer.collect_runtime_health(job_id, "healthy", True, 0)
    elif job[3] == "rejected":
        analyzer.collect_rollback_event(job_id, "validation_failed")
    
    # Save memory
    return analyzer.save_memory(job_id)
