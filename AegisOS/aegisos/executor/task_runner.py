"""Task runner - Runtime Transition Protocol v1.0 with Phase 5 AI governance.

Phase 5: AI execution with budget enforcement.
No system state access. Deterministic.
"""
import time
import sys
import os

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import (
    get_pending_task,
    update_task_status,
    append_task_result
)

# Phase 5: AI governance
from aegisos.ai.executor import execute_with_budget_guard, mock_ai_call


def run_once():
    """Execute exactly one pending task.
    
    Phase 4: Single-shot execution.
    Phase 5: Budget-guarded AI for AI tasks.
    
    Task lifecycle:
        pending → running → completed/failed
    
    Returns:
        task_id if executed, None otherwise
    """
    # Step 1: Fetch one pending task
    task = get_pending_task()
    if task is None:
        return None
    
    task_id = task[0]
    task_type = task[1]
    payload = task[3]
    
    try:
        # Step 2: Mark as running
        update_task_status(task_id, "running")
        
        # Step 3: Execute based on task type
        should_complete = True
        
        # Check for AI task: explicit type "ai" or payload starts with ai indicator
        # Supports: "ai:", "ai：" (Chinese colon), "ai " (space), "AI ", "AI:", "AI："
        payload_lower = payload.lower().strip()
        is_ai_task = (
            task_type == "ai" or 
            (task_type == "command" and (
                payload_lower.startswith("ai:") or      # English colon
                payload_lower.startswith("ai：") or     # Chinese colon (fullwidth)
                payload_lower.startswith("ai ") or      # Space separator
                payload_lower.startswith("kimi:") or    # Kimi prefix
                payload_lower.startswith("kimi ")       # Kimi space
            ))
        )
        
        if is_ai_task:
            # Phase 5: AI task with budget guard
            result, should_complete = _execute_ai_task(task_id, payload)
        else:
            # Phase 4: Mock execution (deterministic)
            result = _execute_mock_task(payload)
        
        # Step 4: Store result
        new_payload = payload + "\nRESULT: " + result
        append_task_result(task_id, new_payload)
        
        # Step 5: Mark status based on execution result
        if should_complete:
            update_task_status(task_id, "completed")
        else:
            update_task_status(task_id, "failed")
        
        return task_id
        
    except Exception as e:
        # Mark failed on exception
        update_task_status(task_id, "failed")
        return task_id


def _execute_mock_task(payload: str) -> str:
    """Execute deterministic mock task (Phase 4)."""
    time.sleep(2)
    return "Executed: " + payload


def _execute_ai_task(task_id: int, payload: str) -> tuple[str, bool]:
    """Execute AI task with budget guard (Phase 5).
    
    Budget validation happens before AI call.
    Rejected tasks are logged to ledger with status='rejected'.
    
    Returns:
        (result_message, should_complete)
    """
    # Extract prompt (remove "ai:" prefix if present)
    prompt = payload
    if prompt.lower().startswith("ai:"):
        prompt = prompt[3:].strip()
    
    # Execute with budget guard
    success, response = execute_with_budget_guard(
        task_id=task_id,
        model="kimi",
        prompt=prompt,
        ai_call_func=mock_ai_call
    )
    
    if success:
        return "AI_" + response, True
    else:
        # Budget rejected or AI error - should not mark as completed
        return response, False
