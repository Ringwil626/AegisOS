"""State Builder - Prompt Contract v1.0 Implementation.

Design Principle:
- Prompt is MACHINE CONTRACT, not chat message
- Deterministic AI syscall layer
- All prompt generation centralized here
- Versioned for governance and reproducibility

Responsibility:
- Compile task → Contract Prompt (5-block structure)
- Enforce strict output schema
- NO AI logic - only text construction

Contract Structure (immutable order):
    [SYSTEM_ROLE]
    [EXECUTION_RULES]  
    [CONTEXT_STATE]
    [TASK_DEFINITION]
    [OUTPUT_SCHEMA]

Version: 1.0
"""
import os
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


# Prompt Contract Version - for governance and reproducibility
PROMPT_VERSION = "1.0"


class ActionType(Enum):
    """Allowed action types - whitelist only."""
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_TEST = "run_test"
    ANALYZE_CODE = "analyze_code"
    GENERATE_PATCH = "generate_patch"


@dataclass(frozen=True)
class TaskDefinition:
    """Structured task definition for Contract Prompt.
    
    Frozen - immutable once created.
    """
    action: ActionType
    inputs: Dict[str, Any]
    
    def validate(self) -> Tuple[bool, str]:
        """Validate task definition before building prompt."""
        if not self.inputs:
            return False, "Task inputs cannot be empty"
        
        # Action-specific validation
        if self.action in [ActionType.CREATE_FILE, ActionType.MODIFY_FILE]:
            if "file_path" not in self.inputs:
                return False, f"{self.action.value} requires 'file_path' input"
            if "content" not in self.inputs and "new_code" not in self.inputs:
                return False, f"{self.action.value} requires 'content' or 'new_code' input"
        
        elif self.action == ActionType.DELETE_FILE:
            if "file_path" not in self.inputs:
                return False, "delete_file requires 'file_path' input"
        
        elif self.action == ActionType.RUN_TEST:
            if "test_command" not in self.inputs:
                return False, "run_test requires 'test_command' input"
        
        elif self.action == ActionType.ANALYZE_CODE:
            if "file_path" not in self.inputs:
                return False, "analyze_code requires 'file_path' input"
        
        return True, ""


class PromptContractBuilder:
    """Builds Contract Prompts following v1.0 specification.
    
    This is the ONLY place where prompts are constructed.
    All AI interaction goes through this contract.
    
    Usage:
        builder = PromptContractBuilder(project="my_app")
        prompt = builder.build_contract_prompt(
            task_id="task_001",
            action=ActionType.CREATE_FILE,
            inputs={"file_path": "main.py", "content": "..."},
            context_state={"runtime_version": "v1.0"}
        )
    """
    
    # Contract blocks - order is IMMUTABLE
    BLOCK_SYSTEM_ROLE = "[SYSTEM_ROLE]"
    BLOCK_EXECUTION_RULES = "[EXECUTION_RULES]"
    BLOCK_CONTEXT_STATE = "[CONTEXT_STATE]"
    BLOCK_TASK_DEFINITION = "[TASK_DEFINITION]"
    BLOCK_OUTPUT_SCHEMA = "[OUTPUT_SCHEMA]"
    
    def __init__(self, project: str, project_path: Optional[str] = None):
        """Initialize builder for a project.
        
        Args:
            project: Project identifier
            project_path: Base path for project files
        """
        self.project = project
        self.project_path = Path(project_path) if project_path else Path(f"projects/{project}")
    
    def _build_system_role(self) -> str:
        """Build [SYSTEM_ROLE] block.
        
        Defines model identity - not AI, but system component.
        """
        return f"""{self.BLOCK_SYSTEM_ROLE}
You are an execution engine inside AegisOS.
You do not explain.
You do not chat.
You do not suggest improvements.
You only produce structured output strictly matching OUTPUT_SCHEMA."""
    
    def _build_execution_rules(self) -> str:
        """Build [EXECUTION_RULES] block.
        
        Hard constraints to prevent model "creativity".
        """
        return f"""{self.BLOCK_EXECUTION_RULES}
Rules:
1. Output must be valid JSON only.
2. No markdown.
3. No commentary.
4. No extra fields.
5. If task cannot be completed, return failure schema.
6. Never ask questions.
7. Never assume missing data.
8. Deterministic execution only.
9. Prompt Version: {PROMPT_VERSION}"""
    
    def _build_context_state(
        self,
        task_id: str,
        runtime_version: str = "v1.0",
        environment: str = "production",
        working_dir: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build [CONTEXT_STATE] block.
        
        Objective state only - no descriptive language.
        """
        lines = [
            self.BLOCK_CONTEXT_STATE,
            f"Project: {self.project}",
            f"Runtime Version: {runtime_version}",
            f"Task ID: {task_id}",
            f"Environment: {environment}",
            f"Prompt Version: {PROMPT_VERSION}",
        ]
        
        if working_dir:
            lines.append(f"Working Directory: {working_dir}")
        else:
            lines.append(f"Working Directory: {self.project_path}")
        
        # Add extra context (objective facts only)
        if extra_context:
            for key, value in extra_context.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def _build_task_definition(
        self,
        action: ActionType,
        inputs: Dict[str, Any]
    ) -> str:
        """Build [TASK_DEFINITION] block.
        
        Structured action + inputs only.
        NO natural language task descriptions.
        """
        lines = [
            self.BLOCK_TASK_DEFINITION,
            f"Action: {action.value}",
            "",
            "Inputs:"
        ]
        
        # Format inputs as key: value
        for key, value in inputs.items():
            if isinstance(value, str):
                # Multi-line strings use | notation
                if '\n' in value:
                    lines.append(f"{key}: |")
                    for line in value.split('\n'):
                        lines.append(f"  {line}")
                else:
                    lines.append(f"{key}: {value}")
            elif isinstance(value, (list, dict)):
                lines.append(f"{key}: {json.dumps(value)}")
            else:
                lines.append(f"{key}: {value}")
        
        return "\n".join(lines)
    
    def _build_output_schema(self) -> str:
        """Build [OUTPUT_SCHEMA] block.
        
        EXACT structure - AI must obey this schema.
        """
        return f"""{self.BLOCK_OUTPUT_SCHEMA}
Return JSON with EXACT structure:

{{
  "status": "success | failure",
  "prompt_version": "{PROMPT_VERSION}",
  "artifacts": [
    {{
      "type": "file | log | data",
      "path": "string",
      "content": "string"
    }}
  ],
  "errors": [
    {{
      "code": "string",
      "message": "string"
    }}
  ],
  "metrics": {{
    "confidence": "high | medium | low"
  }}
}}

Rules for output:
- status must be exactly "success" or "failure"
- prompt_version must be exactly "{PROMPT_VERSION}"
- artifacts array contains created/modified files
- errors array empty on success, populated on failure
- metrics.confidence indicates execution confidence
- NO extra fields allowed
- NO markdown in content fields"""
    
    def build_contract_prompt(
        self,
        task_id: str,
        action: ActionType,
        inputs: Dict[str, Any],
        runtime_version: str = "v1.0",
        environment: str = "production",
        working_dir: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build complete Contract Prompt v1.0.
        
        This is the ONLY way to construct prompts in AegisOS.
        
        Args:
            task_id: Unique task identifier
            action: Action type from whitelist
            inputs: Structured action inputs
            runtime_version: AegisOS runtime version
            environment: execution environment
            working_dir: Working directory path
            extra_context: Additional objective state
            
        Returns:
            Complete Contract Prompt string
            
        Raises:
            ValueError: If task definition is invalid
        """
        # Validate task definition
        task_def = TaskDefinition(action=action, inputs=inputs)
        is_valid, error_msg = task_def.validate()
        if not is_valid:
            raise ValueError(f"Invalid task definition: {error_msg}")
        
        # Build all blocks in IMMUTABLE order
        blocks = [
            self._build_system_role(),
            "",
            self._build_execution_rules(),
            "",
            self._build_context_state(
                task_id=task_id,
                runtime_version=runtime_version,
                environment=environment,
                working_dir=working_dir,
                extra_context=extra_context
            ),
            "",
            self._build_task_definition(action=action, inputs=inputs),
            "",
            self._build_output_schema()
        ]
        
        return "\n".join(blocks)
    
    # Legacy method for backward compatibility
    def build_prompt(
        self,
        instruction: str,
        file_context: Optional[Dict[str, str]] = None,
        constraints: Optional[Dict[str, Any]] = None
    ) -> str:
        """Legacy prompt builder - wraps Contract Prompt.
        
        DEPRECATED: Use build_contract_prompt() for new code.
        
        This method converts legacy instruction-style to Contract Prompt.
        """
        # Convert instruction to structured task
        action = ActionType.CREATE_FILE  # Default assumption
        inputs = {
            "instruction": instruction,
            "file_context": file_context or {},
            "constraints": constraints or {}
        }
        
        # Generate task_id if not provided
        import time
        task_id = f"legacy_{int(time.time())}"
        
        return self.build_contract_prompt(
            task_id=task_id,
            action=action,
            inputs=inputs,
            extra_context={"mode": "legacy"}
        )
    
    def build_simple_prompt(self, instruction: str) -> str:
        """Simple prompt - for basic tasks."""
        import time
        task_id = f"simple_{int(time.time())}"
        
        return self.build_contract_prompt(
            task_id=task_id,
            action=ActionType.ANALYZE_CODE,
            inputs={"instruction": instruction}
        )


# Legacy exports for backward compatibility

class ActionSchemaBuilder:
    """Builds structured action schemas for AI output validation."""
    
    @staticmethod
    def create_file_action(file: str, content: str) -> Dict[str, Any]:
        """Create a create_file action."""
        return {
            "type": "create_file",
            "file": file,
            "content": content
        }
    
    @staticmethod
    def edit_file_action(file: str, content: str, line_start: Optional[int] = None) -> Dict[str, Any]:
        """Create an edit_file action."""
        action = {
            "type": "edit_file",
            "file": file,
            "content": content
        }
        if line_start is not None:
            action["line_start"] = line_start
        return action
    
    @staticmethod
    def delete_file_action(file: str) -> Dict[str, Any]:
        """Create a delete_file action."""
        return {
            "type": "delete_file",
            "file": file
        }
    
    @staticmethod
    def shell_command_action(command: str, timeout: int = 30) -> Dict[str, Any]:
        """Create a shell_command action."""
        return {
            "type": "shell_command",
            "command": command,
            "timeout": timeout
        }
    
    @staticmethod
    def validate_action_schema(data: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate action schema structure.
        
        Returns:
            (is_valid, error_message)
        """
        if not isinstance(data, dict):
            return False, "Root must be a dict"
        
        # Contract v1.0 output schema validation
        if "status" not in data:
            return False, "Missing 'status' field (required in v1.0)"
        
        if data["status"] not in ["success", "failure"]:
            return False, f"Invalid status: {data['status']}"
        
        if "prompt_version" not in data:
            return False, "Missing 'prompt_version' field (required in v1.0)"
        
        if "artifacts" not in data:
            return False, "Missing 'artifacts' array"
        
        if not isinstance(data["artifacts"], list):
            return False, "'artifacts' must be an array"
        
        # Validate each artifact
        for i, artifact in enumerate(data["artifacts"]):
            if not isinstance(artifact, dict):
                return False, f"Artifact[{i}] must be an object"
            if "type" not in artifact:
                return False, f"Artifact[{i}] missing 'type'"
            if "path" not in artifact:
                return False, f"Artifact[{i}] missing 'path'"
        
        # Check errors on failure
        if data["status"] == "failure":
            if "errors" not in data or not data["errors"]:
                return False, "Failure status requires 'errors' array"
        
        return True, "Valid"


# Convenience functions (backward compatible)

def build_prompt(
    project: str,
    instruction: str,
    project_path: Optional[str] = None,
    file_context: Optional[Dict[str, str]] = None,
    constraints: Optional[Dict[str, Any]] = None
) -> str:
    """Convenience function to build prompt without instantiating builder.
    
    DEPRECATED: Use PromptContractBuilder.build_contract_prompt() for new code.
    """
    builder = PromptContractBuilder(project=project, project_path=project_path)
    return builder.build_prompt(
        instruction=instruction,
        file_context=file_context,
        constraints=constraints
    )


def validate_action_schema(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Convenience function to validate action schema."""
    return ActionSchemaBuilder.validate_action_schema(data)


def build_contract_prompt(
    project: str,
    task_id: str,
    action: str,
    inputs: Dict[str, Any],
    **kwargs
) -> str:
    """Build Contract Prompt v1.0 (new interface).
    
    Args:
        project: Project identifier
        task_id: Unique task ID
        action: Action type string (from whitelist)
        inputs: Action inputs dict
        **kwargs: Additional context
        
    Returns:
        Contract Prompt string
    """
    builder = PromptContractBuilder(project=project)
    
    # Convert string action to enum
    try:
        action_enum = ActionType(action)
    except ValueError:
        raise ValueError(f"Invalid action: {action}. Must be one of: {[a.value for a in ActionType]}")
    
    return builder.build_contract_prompt(
        task_id=task_id,
        action=action_enum,
        inputs=inputs,
        **kwargs
    )
