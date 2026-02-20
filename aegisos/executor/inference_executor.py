"""Inference Executor - Prompt Contract v1.0 Integration.

This is the integration layer that connects:
- core/state_builder: Builds Contract Prompts v1.0
- infra/kimi_client: Executes inference (stateless)
- core/validator: Validates Contract outputs
- audit/usage_logger: Records costs

AegisOS Call Path:
    Supervisor
       ↓
    Fetch pending task
       ↓
    InferenceExecutor.execute()
       ↓
    state_builder.build_contract_prompt()
       ↓
    Budget Check (Phase5)
       ↓
    kimi_client.run_inference()
       ↓
    validator.strict_validate()  ← Enforces Contract v1.0
       ↓
    audit.usage_logger.log_inference_usage()
       ↓
    Mark task complete

Note: Kimi never knows the system exists.
Version: Prompt Contract v1.0
"""
import os
import sys
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Add project root to path
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

# Internal provider - NOT a public API
from aegisos.executor._inference_provider import (
    InferenceRequest,
    InferenceResult,
    run_inference as _run_inference,
    check_configuration as _check_inference_config
)
from aegisos.core.state_builder import (
    PromptContractBuilder,
    ActionType,
    build_contract_prompt
)
from aegisos.core.validator import (
    ContractSchemaValidator,
    ValidationResult,
    strict_validate,
    ProtocolViolation
)
from aegisos.audit.usage_logger import (
    log_inference_usage,
    log_inference_rejection,
    log_inference_failure
)
from aegisos.db.ledger import check_daily_budget


class ContractInferenceExecutor:
    """High-level executor for AI inference tasks using Prompt Contract v1.0.
    
    Orchestrates the complete inference pipeline:
    1. Build Contract Prompt (5-block structure)
    2. Check budget (Phase5 guard)
    3. Execute inference
    4. Validate Contract output (strict schema check)
    5. Log usage
    
    Usage:
        executor = ContractInferenceExecutor(project="my_app")
        result = executor.execute_contract(
            task_id="task_001",
            action=ActionType.CREATE_FILE,
            inputs={"file_path": "main.py", "content": "..."}
        )
        
        if result.success:
            data = json.loads(result.output_text)
            # data follows Contract v1.0 schema
    """
    
    def __init__(self, project: str, project_path: Optional[str] = None):
        """Initialize executor for a project.
        
        Args:
            project: Project identifier
            project_path: Base path for project files
        """
        self.project = project
        self.project_path = project_path or f"projects/{project}"
        self.builder = PromptContractBuilder(
            project=project,
            project_path=self.project_path
        )
    
    def execute_contract(
        self,
        task_id: str,
        action: ActionType,
        inputs: Dict[str, Any],
        model: str = "kimi-k2.5",
        temperature: float = 1.0,
        max_tokens: int = 4000,
        timeout_sec: int = 300,
        runtime_version: str = "v1.0",
        environment: str = "production",
        metadata: Optional[Dict[str, Any]] = None
    ) -> InferenceResult:
        """Execute inference using Prompt Contract v1.0.
        
        This is the PRIMARY interface for AI inference in AegisOS.
        
        Args:
            task_id: Unique task identifier
            action: Action type from whitelist (ActionType enum)
            inputs: Structured action inputs
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Max output tokens
            timeout_sec: Timeout in seconds
            runtime_version: AegisOS runtime version
            environment: Execution environment
            metadata: Additional metadata for audit
            
        Returns:
            InferenceResult with Contract v1.0 compliant output
            
        Note:
            Even on validation failure, returns InferenceResult.
            Check success flag and error field.
        """
        # Step 1: Build Contract Prompt
        try:
            prompt = self.builder.build_contract_prompt(
                task_id=task_id,
                action=action,
                inputs=inputs,
                runtime_version=runtime_version,
                environment=environment,
                extra_context=metadata
            )
        except ValueError as e:
            # Invalid task definition
            return InferenceResult(
                task_id=task_id,
                success=False,
                output_text="",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=0,
                error=f"INVALID_TASK_DEFINITION: {e}"
            )
        
        # Step 2: Check budget (Phase5 guard)
        estimated_tokens = len(prompt) // 4 + max_tokens
        allowed, reason = check_daily_budget(model, estimated_tokens)
        
        if not allowed:
            log_inference_rejection(
                task_id=task_id,
                model=model,
                reason=reason,
                estimated_tokens=estimated_tokens
            )
            return InferenceResult(
                task_id=task_id,
                success=False,
                output_text="",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=0,
                error=f"BUDGET_REJECTED: {reason}"
            )
        
        # Step 3: Execute inference
        request = InferenceRequest(
            task_id=task_id,
            project=self.project,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            prompt=prompt,
            metadata={
                "action": action.value,
                **(metadata or {})
            }
        )
        
        result = _run_inference(request)
        
        # Step 4: Validate Contract output (strict)
        if result.success:
            validation = ContractSchemaValidator.validate(result.output_text)
            
            if not validation.is_valid:
                # AI violated Prompt Contract
                result = InferenceResult(
                    task_id=task_id,
                    success=False,
                    output_text=result.output_text,
                    usage=result.usage,
                    latency_ms=result.latency_ms,
                    error=f"AI_PROTOCOL_VIOLATION: [{validation.error_code}] {validation.error_message}"
                )
                log_inference_failure(
                    task_id=task_id,
                    model=model,
                    error=f"Contract violation: {validation.error_message}",
                    prompt_tokens=result.usage.get("prompt_tokens", 0)
                )
            else:
                # Validation passed - log success
                log_inference_usage(
                    task_id=task_id,
                    model=model,
                    usage=result.usage,
                    latency_ms=result.latency_ms,
                    metadata={
                        "action": action.value,
                        "contract_version": "1.0",
                        **(metadata or {})
                    },
                    status="committed"
                )
        else:
            # Inference failed - log failure
            log_inference_failure(
                task_id=task_id,
                model=model,
                error=result.error or "Unknown error",
                prompt_tokens=result.usage.get("prompt_tokens", 0)
            )
        
        return result
    
    def execute_file_creation(
        self,
        task_id: str,
        file_path: str,
        content: str,
        **kwargs
    ) -> InferenceResult:
        """Convenience method for file creation tasks."""
        return self.execute_contract(
            task_id=task_id,
            action=ActionType.CREATE_FILE,
            inputs={"file_path": file_path, "content": content},
            **kwargs
        )
    
    def execute_file_modification(
        self,
        task_id: str,
        file_path: str,
        new_code: str,
        **kwargs
    ) -> InferenceResult:
        """Convenience method for file modification tasks."""
        return self.execute_contract(
            task_id=task_id,
            action=ActionType.MODIFY_FILE,
            inputs={"file_path": file_path, "new_code": new_code},
            **kwargs
        )
    
    def execute_code_analysis(
        self,
        task_id: str,
        file_path: str,
        **kwargs
    ) -> InferenceResult:
        """Convenience method for code analysis tasks."""
        return self.execute_contract(
            task_id=task_id,
            action=ActionType.ANALYZE_CODE,
            inputs={"file_path": file_path},
            **kwargs
        )


# Legacy InferenceExecutor for backward compatibility

class InferenceExecutor(ContractInferenceExecutor):
    """Legacy executor - extends ContractInferenceExecutor."""
    
    def execute(
        self,
        task_id: str,
        instruction: str,
        model: str = "kimi-k2.5",
        temperature: float = 1.0,
        max_tokens: int = 4000,
        timeout_sec: int = 300,
        file_context: Optional[Dict[str, str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> InferenceResult:
        """Legacy execute method - wraps Contract execution.
        
        DEPRECATED: Use execute_contract() for new code.
        
        Converts legacy instruction-style to Contract Prompt.
        """
        # Convert instruction to Contract action
        inputs = {
            "instruction": instruction,
            "file_context": file_context or {},
            "constraints": constraints or {}
        }
        
        return self.execute_contract(
            task_id=task_id,
            action=ActionType.ANALYZE_CODE,  # Default action for legacy
            inputs=inputs,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_sec=timeout_sec,
            metadata={"mode": "legacy", **(metadata or {})}
        )
    
    def execute_simple(
        self,
        task_id: str,
        instruction: str,
        model: str = "kimi-k2.5"
    ) -> InferenceResult:
        """Simplified execution - for basic tasks."""
        return self.execute(
            task_id=task_id,
            instruction=instruction,
            model=model
        )


# Convenience functions

def execute_contract_inference(
    task_id: str,
    project: str,
    action: str,
    inputs: Dict[str, Any],
    **kwargs
) -> InferenceResult:
    """One-shot Contract inference execution.
    
    Example:
        result = execute_contract_inference(
            task_id="task_001",
            project="my_app",
            action="create_file",
            inputs={"file_path": "main.py", "content": "..."}
        )
        
        if result.success:
            data = json.loads(result.output_text)
            # data follows Contract v1.0 schema
    """
    executor = ContractInferenceExecutor(project=project)
    
    # Convert string action to enum
    try:
        action_enum = ActionType(action)
    except ValueError:
        raise ValueError(f"Invalid action: {action}. Must be one of: {[a.value for a in ActionType]}")
    
    return executor.execute_contract(
        task_id=task_id,
        action=action_enum,
        inputs=inputs,
        **kwargs
    )


def execute_inference(
    task_id: str,
    project: str,
    instruction: str,
    model: str = "kimi-k2.5",
    file_context: Optional[Dict[str, str]] = None,
    project_path: Optional[str] = None
) -> InferenceResult:
    """Legacy one-shot inference (backward compatible)."""
    executor = InferenceExecutor(project=project, project_path=project_path)
    return executor.execute(
        task_id=task_id,
        instruction=instruction,
        model=model,
        file_context=file_context
    )


def check_system_ready() -> Tuple[bool, str]:
    """Check if inference system is ready for use."""
    # Check inference config
    inference_ok, inference_msg = _check_inference_config()
    if not inference_ok:
        return False, f"Inference not ready: {inference_msg}"
    
    # Check state builder
    try:
        from aegisos.core.state_builder import PromptContractBuilder
    except ImportError as e:
        return False, f"StateBuilder not available: {e}"
    
    # Check validator
    try:
        from aegisos.core.validator import ContractSchemaValidator
    except ImportError as e:
        return False, f"Validator not available: {e}"
    
    # Check audit logger
    try:
        from aegisos.audit.usage_logger import log_inference_usage
    except ImportError as e:
        return False, f"UsageLogger not available: {e}"
    
    return True, "Inference system ready (Prompt Contract v1.0)"


# Backward compatibility shim
def run_task_with_contract(
    task_id: str,
    instruction: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str, Dict[str, int]]:
    """Backward-compatible interface using new contract.
    
    Returns:
        (success, output_text, usage_dict)
    """
    project = (context or {}).get("project_name", "default")
    
    executor = InferenceExecutor(project=project)
    result = executor.execute(
        task_id=task_id,
        instruction=instruction,
        metadata=context
    )
    
    return result.success, result.output_text, result.usage
