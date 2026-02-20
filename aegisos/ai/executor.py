"""AI Executor - Budget-guarded AI execution.

Phase 5: AI calls must pass budget validation before execution.
No system_state access. No ledger bypass.
"""
import time
from typing import Callable

from aegisos.db.ledger import (
    init_ai_ledger,
    check_daily_budget,
    log_ai_usage,
    estimate_cost,
    MODEL_PRICING
)


def init_ai_system():
    """Initialize AI accounting system."""
    init_ai_ledger()


def execute_with_budget_guard(task_id: int, model: str, prompt: str,
                               ai_call_func: Callable[[str], tuple[str, int, int]]) -> tuple[bool, str]:
    """Execute AI call with budget validation.
    
    Args:
        task_id: Task ID for ledger
        model: Model to use
        prompt: Input prompt
        ai_call_func: Function(prompt) -> (response, prompt_tokens, completion_tokens)
    
    Returns:
        (success, response_or_error)
    """
    # Step 1: Estimate tokens (rough heuristic: 1 token ~ 4 chars)
    estimated_tokens = len(prompt) // 4
    estimated_completion = min(estimated_tokens, 4096)  # Assume up to 4K output
    estimated_total = estimated_tokens + estimated_completion
    
    # Step 2: Budget validation
    allowed, reason = check_daily_budget(model, estimated_total)
    if not allowed:
        # Log rejection
        log_ai_usage(task_id, model, estimated_tokens, 0, status="rejected")
        return False, f"BUDGET_REJECTED: {reason}"
    
    # Step 3: Execute AI call
    try:
        response, prompt_tokens, completion_tokens = ai_call_func(prompt)
        
        # Step 4: Log actual usage
        log_ai_usage(task_id, model, prompt_tokens, completion_tokens, status="committed")
        
        return True, response
        
    except Exception as e:
        # Log failure with zero tokens
        log_ai_usage(task_id, model, 0, 0, status="failed")
        return False, f"AI_ERROR: {str(e)}"


def mock_ai_call(prompt: str) -> tuple[str, int, int]:
    """Mock AI call for testing without real API.
    
    Returns deterministic response with simulated token counts.
    """
    import time
    time.sleep(0.5)  # Simulate latency
    
    prompt_tokens = len(prompt) // 4
    response_text = f"MOCK_RESPONSE: Processed {len(prompt)} chars"
    completion_tokens = len(response_text) // 4
    
    return response_text, prompt_tokens, completion_tokens


class BudgetGuard:
    """Context manager for budget-guarded AI execution."""
    
    def __init__(self, task_id: int, model: str):
        self.task_id = task_id
        self.model = model
        self.ledger_id = None
        self.allowed = False
        self.estimated_cost = 0.0
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.allowed and not self.ledger_id:
            # Budget check failed, already logged
            pass
        return False
    
    def check_budget(self, estimated_tokens: int) -> bool:
        """Check if call is within budget."""
        self.allowed, reason = check_daily_budget(self.model, estimated_tokens)
        if not self.allowed:
            self.ledger_id = log_ai_usage(
                self.task_id, self.model, 
                estimated_tokens, 0, 
                status="rejected"
            )
        return self.allowed
    
    def record_usage(self, prompt_tokens: int, completion_tokens: int):
        """Record successful usage."""
        if self.allowed:
            self.ledger_id = log_ai_usage(
                self.task_id, self.model,
                prompt_tokens, completion_tokens,
                status="committed"
            )
            self.estimated_cost = estimate_cost(self.model, prompt_tokens, completion_tokens)
