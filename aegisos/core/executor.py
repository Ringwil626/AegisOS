"""Executor - Task State Machine Driver with Phase5 Budget Control.

Executor Contract v1.0 + Phase5 AI Usage Accounting

Responsibilities:
1. Budget gate check (Phase5) - BEFORE calling AI
2. Claim one pending task from SQLite (atomic)
3. Execute via Prompt Contract + kimi_client
4. Calculate cost immediately (deterministic)
5. Record to usage_ledger (Single Source of Truth)
6. Advance task state based on result

State Machine:
    pending → running → completed
               ↘
                failed

Version: Executor Contract v1.0 + Phase5
"""
import os
import sys
import json
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

# Add project root to path
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

# Database operations
from aegisos.db.sqlite_store import (
    claim_pending_task,
    update_task_status,
    append_task_result,
    reset_running_tasks_to_pending,
    write_execution_log,
    DB_PATH
)

# Phase5 Usage Accounting
from aegisos.db.usage_ledger import UsageLedger, record_task_usage
from aegisos.db.pricing import calculate_cost

# Prompt Contract
from aegisos.core.state_builder import PromptContractBuilder, ActionType
from aegisos.core.validator import strict_validate, ProtocolViolation

# Inference Contract
from aegisos.executor._inference_provider import InferenceRequest, run_inference


# Executor Contract Version
EXECUTOR_VERSION = "1.0"

# Default timeout window for task recovery (seconds)
DEFAULT_TIMEOUT_WINDOW = 300  # 5 minutes

# Default task timeout for AI inference (seconds)
DEFAULT_INFERENCE_TIMEOUT = 300  # 5 minutes

# Default project
DEFAULT_PROJECT = "aegisos"


class TaskStatus(Enum):
    """Task state machine states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutorError(Exception):
    """Executor operation error."""
    pass


@dataclass
class ExecutionResult:
    """Result of single task execution."""
    task_id: int
    success: bool
    status: TaskStatus
    artifacts_count: int
    tokens_used: int
    latency_ms: int
    cost_estimate: float
    error: Optional[str] = None


class TaskStateMachine:
    """Pure state machine for task lifecycle."""
    
    @staticmethod
    def can_transition(from_status: TaskStatus, to_status: TaskStatus) -> bool:
        """Check if state transition is valid."""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.RUNNING},
            TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
            TaskStatus.COMPLETED: set(),
            TaskStatus.FAILED: set(),
        }
        return to_status in valid_transitions.get(from_status, set())
    
    @staticmethod
    def transition(task_id: int, to_status: TaskStatus, 
                   result_data: Optional[str] = None) -> bool:
        """Execute state transition."""
        try:
            update_task_status(task_id, to_status.value)
            if result_data:
                append_task_result(task_id, result_data)
            return True
        except Exception as e:
            print(f"[Executor] State transition failed: {e}")
            return False


class ArtifactApplier:
    """Mechanically apply artifacts from AI output."""
    
    @staticmethod
    def apply_artifacts(artifacts: list, project_path: str) -> Tuple[bool, str]:
        """Apply artifacts to filesystem."""
        from pathlib import Path
        
        project = Path(project_path)
        
        for artifact in artifacts:
            art_type = artifact.get("type")
            path = artifact.get("path")
            content = artifact.get("content", "")
            
            if not path:
                return False, "Artifact missing path"
            
            # Security: Ensure path is within project
            full_path = project / path
            try:
                full_path = full_path.resolve()
                project_resolved = project.resolve()
                if not str(full_path).startswith(str(project_resolved)):
                    return False, f"Path traversal detected: {path}"
            except Exception as e:
                return False, f"Path resolution error: {e}"
            
            try:
                if art_type == "file":
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding='utf-8')
                elif art_type == "log":
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(full_path, 'a', encoding='utf-8') as f:
                        f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {content}\n")
                elif art_type == "data":
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    if isinstance(content, (dict, list)):
                        content = json.dumps(content, indent=2)
                    full_path.write_text(content, encoding='utf-8')
                else:
                    return False, f"Unknown artifact type: {art_type}"
            except Exception as e:
                return False, f"Failed to write {path}: {e}"
        
        return True, ""


class ContractExecutor:
    """Executor Contract v1.0 + Phase5 Budget Control."""
    
    def __init__(self, project: str = DEFAULT_PROJECT, 
                 timeout_window: int = DEFAULT_TIMEOUT_WINDOW):
        """Initialize Executor."""
        self.project = project
        self.project_path = f"projects/{project}"
        self.timeout_window = timeout_window
        self.builder = PromptContractBuilder(project=project)
        
        # Initialize Phase5 tables
        UsageLedger.init_tables()
    
    def cleanup_stuck_tasks(self) -> int:
        """Reset timed-out running tasks to pending."""
        count = reset_running_tasks_to_pending(self.timeout_window)
        if count > 0:
            print(f"[Executor] Reset {count} stuck tasks to pending")
        return count
    
    def _check_budget_gate(self, estimated_tokens: int = 4000) -> Tuple[bool, str]:
        """Phase5: Budget gate check before AI execution.
        
        Hard stop if budget exceeded.
        
        Args:
            estimated_tokens: Estimated tokens for this call
            
        Returns:
            (allowed, reason)
        """
        # Check rate limit first
        allowed, reason = UsageLedger.check_rate_limit(self.project)
        if not allowed:
            return False, f"RATE_LIMIT: {reason}"
        
        # Check budget
        allowed, reason, usage = UsageLedger.check_budget(self.project)
        if not allowed:
            return False, f"BUDGET: {reason}"
        
        return True, ""
    
    def execute_one_task(self) -> Optional[ExecutionResult]:
        """Execute single task with Phase5 accounting."""
        started_at = int(time.time())
        
        # Step 1: Cleanup stuck tasks
        self.cleanup_stuck_tasks()
        
        # Step 2: Claim one pending task
        task = claim_pending_task(self.timeout_window)
        if not task:
            return None
        
        task_id = task[0]
        task_type = task[1]
        payload = task[3] or "{}"
        
        print(f"[Executor] Claimed task #{task_id} (type: {task_type})")
        
        # Parse task payload
        try:
            task_data = json.loads(payload)
        except json.JSONDecodeError:
            task_data = {"instruction": payload}
        
        instruction = task_data.get("instruction", "")
        action_str = task_data.get("action", "analyze_code")
        inputs = task_data.get("inputs", {})
        
        # Extract project from task data or use default
        task_project = task_data.get("project", self.project)
        
        # Execution tracking
        inference_success = False
        schema_valid = False
        artifacts_applied = False
        output_text = ""
        error_message = None
        tokens_prompt = 0
        tokens_completion = 0
        tokens_total = 0
        latency_ms = 0
        cost_estimate = 0.0
        model_used = "kimi-k2.5"
        artifacts = []
        
        try:
            # Step 3: Build Prompt Contract
            try:
                action = ActionType(action_str)
            except ValueError:
                action = ActionType.ANALYZE_CODE
            
            prompt = self.builder.build_contract_prompt(
                task_id=str(task_id),
                action=action,
                inputs=inputs or {"instruction": instruction},
                runtime_version="v1.0",
                environment="production"
            )
            
            # Phase5: Budget gate check BEFORE calling AI
            estimated_tokens = len(prompt) // 4 + 4000
            allowed, reason = self._check_budget_gate(estimated_tokens)
            
            if not allowed:
                raise ExecutorError(f"BUDGET_GATE_BLOCKED: {reason}")
            
            # Step 4: Run inference
            request = InferenceRequest(
                task_id=str(task_id),
                project=task_project,
                model=model_used,
                temperature=1.0,
                max_tokens=4000,
                timeout_sec=DEFAULT_INFERENCE_TIMEOUT,
                prompt=prompt,
                metadata={"task_type": task_type, "project": task_project}
            )
            
            inference_result = run_inference(request)
            output_text = inference_result.output_text
            tokens_prompt = inference_result.usage.get("prompt_tokens", 0)
            tokens_completion = inference_result.usage.get("completion_tokens", 0)
            tokens_total = inference_result.usage.get("total_tokens", tokens_prompt + tokens_completion)
            latency_ms = inference_result.latency_ms
            
            if not inference_result.success:
                raise ExecutorError(f"Inference failed: {inference_result.error}")
            
            inference_success = True
            
            # Step 5: Validate output
            try:
                data = strict_validate(output_text)
                schema_valid = True
                
                if data.get("status") != "success":
                    errors = data.get("errors", [])
                    error_str = "; ".join([e.get("message", "Unknown") for e in errors])
                    raise ExecutorError(f"AI reported failure: {error_str}")
                
                artifacts = data.get("artifacts", [])
                
            except ProtocolViolation as e:
                raise ExecutorError(f"AI protocol violation: {e}")
            
            # Step 6: Apply artifacts
            if artifacts:
                success, error = ArtifactApplier.apply_artifacts(
                    artifacts, self.project_path
                )
                if not success:
                    raise ExecutorError(f"Artifact apply failed: {error}")
                artifacts_applied = True
            else:
                artifacts_applied = True
            
            # Step 7a: Mark completed
            if inference_success and schema_valid and artifacts_applied:
                # Phase5: Calculate cost immediately
                cost_estimate, currency = calculate_cost(
                    model=model_used,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion
                )
                
                # Phase5: Record to usage_ledger
                record_task_usage(
                    task_id=task_id,
                    project=task_project,
                    model=model_used,
                    tokens_prompt=tokens_prompt,
                    tokens_completion=tokens_completion,
                    latency_ms=latency_ms,
                    cost_estimate=cost_estimate
                )
                
                result_payload = json.dumps({
                    "output": output_text,
                    "artifacts_count": len(artifacts),
                    "tokens_used": tokens_total,
                    "cost_estimate": cost_estimate,
                    "latency_ms": latency_ms
                })
                
                TaskStateMachine.transition(
                    task_id, TaskStatus.COMPLETED, result_payload
                )
                
                finished_at = int(time.time())
                write_execution_log(
                    task_id=task_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    success=True,
                    tokens_used=tokens_total,
                    latency_ms=latency_ms
                )
                
                print(f"[Executor] Task #{task_id} completed ({tokens_total} tokens, ${cost_estimate:.4f})")
                
                return ExecutionResult(
                    task_id=task_id,
                    success=True,
                    status=TaskStatus.COMPLETED,
                    artifacts_count=len(artifacts),
                    tokens_used=tokens_total,
                    latency_ms=latency_ms,
                    cost_estimate=cost_estimate
                )
            
        except Exception as e:
            error_message = str(e)
            print(f"[Executor] Task #{task_id} failed: {error_message}")
        
        # Step 7b: Mark failed
        if error_message:
            TaskStateMachine.transition(
                task_id, TaskStatus.FAILED, 
                json.dumps({"error": error_message})
            )
            
            finished_at = int(time.time())
            write_execution_log(
                task_id=task_id,
                started_at=started_at,
                finished_at=finished_at,
                success=False,
                tokens_used=tokens_total,
                latency_ms=latency_ms,
                error=error_message
            )
            
            return ExecutionResult(
                task_id=task_id,
                success=False,
                status=TaskStatus.FAILED,
                artifacts_count=len(artifacts),
                tokens_used=tokens_total,
                latency_ms=latency_ms,
                cost_estimate=cost_estimate,
                error=error_message
            )
        
        return None


def execute_one_task(project: str = DEFAULT_PROJECT) -> Optional[ExecutionResult]:
    """Convenience function to execute one task."""
    executor = ContractExecutor(project=project)
    return executor.execute_one_task()


def get_execution_stats(task_id: int) -> Dict[str, Any]:
    """Get execution statistics for a task."""
    import sqlite3
    from pathlib import Path
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """SELECT task_id, started_at, finished_at, success, 
                  tokens_used, latency_ms, error
           FROM execution_log 
           WHERE task_id = ?
           ORDER BY id DESC""",
        (task_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"task_id": task_id, "executions": []}
    
    executions = []
    for row in rows:
        executions.append({
            "started_at": row[1],
            "finished_at": row[2],
            "success": bool(row[3]),
            "tokens_used": row[4],
            "latency_ms": row[5],
            "error": row[6]
        })
    
    return {
        "task_id": task_id,
        "execution_count": len(executions),
        "executions": executions
    }
