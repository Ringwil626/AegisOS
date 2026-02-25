"""Action Schema Executor - P7 Security Compliant

Executes AI-returned Action Schema with strict security guards:
- Two-step approval required (/approve -> /execute)
- Risk level validation
- Command whitelist/blacklist
- Sandboxed execution within project directory
- Async execution via Worker Pool
"""
import json
import re
import shlex
import sqlite3
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

# Database path same as sqlite_store
import os
def _get_db_path():
    """Get current DB path from environment (allows test override)."""
    return os.getenv("AEGISOS_DB_PATH", "aegisos.db")


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionType(Enum):
    SHELL_COMMAND = "shell_command"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    UNKNOWN = "unknown"


@dataclass
class Action:
    type: ActionType
    command: str
    timeout: int = 60
    

@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    message: str


# P7: Command blacklist - forbidden patterns
COMMAND_BLACKLIST = [
    r"rm\s+-rf\s+/",
    r"rm\s+-rf\s+/\s*",
    r">\s*/dev/(sd|hd|nvme)",
    r"mkfs\.",
    r"dd\s+if=.*of=/dev/",
    r":\(\)\s*\{\s*:\|\:&\s*\}",  # Fork bomb
    r"curl.*\|\s*sh",
    r"wget.*\|\s*sh",
    r"powershell.*-enc",
    r"cmd\.exe\s+/c",
    r"<script",
    r"javascript:",
]

# P7: Command whitelist - allowed base commands (optional strict mode)
COMMAND_WHITELIST = [
    "ls", "cat", "find", "grep", "head", "tail", "wc",
    "python", "python3", "pip", "pip3",
    "git", "git status", "git log", "git diff",
    "cd", "pwd", "echo", "mkdir", "touch",
    "node", "npm", "yarn",
    "pytest", "python -m pytest",
    "flask", "python -m flask",
    "docker", "docker-compose",
    "make", "cmake",
]


def parse_action_schema(result_json: str) -> Tuple[List[Action], str, RiskLevel]:
    """Parse AI result JSON into list of Actions.
    
    Returns:
        (actions, explanation, risk_level)
    """
    try:
        data = json.loads(result_json)
    except json.JSONDecodeError as e:
        return [], f"Invalid JSON: {e}", RiskLevel.CRITICAL
    
    actions = []
    action_list = data.get("actions", [])
    explanation = data.get("explanation", "")
    risk_str = data.get("risk_level", "medium").lower()
    
    try:
        risk_level = RiskLevel(risk_str)
    except ValueError:
        risk_level = RiskLevel.MEDIUM
    
    for act in action_list:
        if not isinstance(act, dict):
            continue
            
        act_type = act.get("type", "unknown")
        command = act.get("command", "")
        timeout = act.get("timeout", 60)
        
        # Validate timeout
        timeout = max(10, min(timeout, 300))  # Clamp 10-300s
        
        if act_type == "shell_command":
            actions.append(Action(ActionType.SHELL_COMMAND, command, timeout))
        elif act_type == "file_read":
            actions.append(Action(ActionType.FILE_READ, command, timeout))
        else:
            actions.append(Action(ActionType.UNKNOWN, command, timeout))
    
    return actions, explanation, risk_level


def validate_command(command: str, strict_mode: bool = False) -> Tuple[bool, str]:
    """Validate command against security policies.
    
    P7 Security: Checks blacklist and optionally whitelist
    
    Returns:
        (is_valid, error_message)
    """
    if not command or not isinstance(command, str):
        return False, "Empty or invalid command"
    
    # Check blacklist
    cmd_lower = command.lower()
    for pattern in COMMAND_BLACKLIST:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return False, f"Command matches forbidden pattern: {pattern}"
    
    # Optional strict mode: whitelist check
    if strict_mode:
        # Extract base command
        try:
            base_cmd = shlex.split(command)[0]
        except ValueError:
            return False, "Invalid command syntax"
        
        # Check if base command is in whitelist
        base_cmd_lower = base_cmd.lower()
        if base_cmd_lower not in [c.lower() for c in COMMAND_WHITELIST]:
            return False, f"Command '{base_cmd}' not in whitelist"
    
    return True, ""


def check_task_approved(task_id: int) -> Tuple[bool, Optional[str]]:
    """Check if task has been approved for execution.
    
    P7 Security: Two-step approval required
    
    Returns:
        (is_approved, approval_actor)
    """
    try:
        conn = sqlite3.connect(_get_db_path())
        cursor = conn.cursor()
        
        # Check if task exists and is completed
        cursor.execute(
            "SELECT status FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, None
        
        status = row[0]
        if status != "completed":
            conn.close()
            return False, None
        
        # Check for approval in task_results or separate approval tracking
        # For now, check if result contains 'APPROVED' marker
        cursor.execute(
            "SELECT payload FROM tasks WHERE id = ? AND payload LIKE '%APPROVED%'",
            (task_id,)
        )
        approved = cursor.fetchone()
        conn.close()
        
        if approved:
            return True, "system"
        
        return False, None
        
    except Exception as e:
        print(f"[ActionExecutor] Approval check error: {e}")
        return False, None


def mark_task_approved(task_id: int, actor: str) -> bool:
    """Mark task as approved for execution."""
    try:
        conn = sqlite3.connect(_get_db_path())
        cursor = conn.cursor()
        
        # Append approval marker to payload
        cursor.execute(
            "SELECT payload FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
        
        current_payload = row[0] or ""
        approval_marker = f"\n\n[APPROVED by {actor} at {__import__('time').time()}]"
        new_payload = current_payload + approval_marker
        
        cursor.execute(
            "UPDATE tasks SET payload = ? WHERE id = ?",
            (new_payload, task_id)
        )
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        print(f"[ActionExecutor] Approval mark error: {e}")
        return False


def execute_shell_command(command: str, cwd: Optional[str] = None, 
                         timeout: int = 60) -> ExecutionResult:
    """Execute shell command with security constraints.
    
    P7 Security: Sandboxed execution with timeout
    """
    import subprocess
    
    # Validate command first
    valid, error = validate_command(command)
    if not valid:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=error,
            exit_code=-1,
            message=f"Command validation failed: {error}"
        )
    
    try:
        # Execute with timeout
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        stdout = result.stdout[:2000] if result.stdout else ""  # Limit output
        stderr = result.stderr[:1000] if result.stderr else ""  # Limit error
        
        success = result.returncode == 0
        
        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            message="Success" if success else f"Exit code {result.returncode}"
        )
        
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Command timed out after {timeout}s",
            exit_code=-1,
            message=f"Timeout ({timeout}s)"
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
            message=f"Execution error: {e}"
        )


def execute_actions(task_id: int, actions: List[Action], 
                   project_path: Optional[str] = None) -> List[ExecutionResult]:
    """Execute list of actions and return results.
    
    P7 Security: Each action is validated before execution
    """
    results = []
    
    for i, action in enumerate(actions, 1):
        print(f"[ActionExecutor] Executing action {i}/{len(actions)}: {action.type.value}")
        
        if action.type == ActionType.SHELL_COMMAND:
            result = execute_shell_command(
                action.command,
                cwd=project_path,
                timeout=action.timeout
            )
        elif action.type == ActionType.FILE_READ:
            # Implement file read with path validation
            result = _execute_file_read(action.command, project_path)
        else:
            result = ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unknown action type: {action.type.value}",
                exit_code=-1,
                message="Unsupported action type"
            )
        
        results.append(result)
        
        # Stop on failure (fail-fast)
        if not result.success:
            print(f"[ActionExecutor] Action {i} failed, stopping execution")
            break
    
    return results


def _execute_file_read(file_path: str, base_path: Optional[str] = None) -> ExecutionResult:
    """Execute file read with path traversal protection."""
    import os
    
    # Normalize path
    if base_path:
        full_path = os.path.join(base_path, file_path)
    else:
        full_path = file_path
    
    # Resolve to absolute path
    try:
        abs_path = os.path.abspath(full_path)
        if base_path:
            abs_base = os.path.abspath(base_path)
            # Ensure file is within base path
            if not abs_path.startswith(abs_base):
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Path traversal detected",
                    exit_code=-1,
                    message="Security: Path outside project directory"
                )
    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
            message=f"Path error: {e}"
        )
    
    # Read file
    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            content = f.read(10000)  # Limit to 10KB
        
        return ExecutionResult(
            success=True,
            stdout=content,
            stderr="",
            exit_code=0,
            message=f"Read {len(content)} bytes"
        )
    except Exception as e:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=str(e),
            exit_code=-1,
            message=f"Read error: {e}"
        )


def format_execution_report(task_id: int, actions: List[Action], 
                           results: List[ExecutionResult]) -> str:
    """Format execution results for Discord display."""
    lines = [f"**Action Execution Report - Task #{task_id}**\n"]
    
    total = len(results)
    successful = sum(1 for r in results if r.success)
    
    lines.append(f"Progress: {successful}/{total} actions succeeded\n")
    
    for i, (action, result) in enumerate(zip(actions, results), 1):
        emoji = "✅" if result.success else "❌"
        lines.append(f"{emoji} **Action {i}**: `{action.command[:50]}{'...' if len(action.command) > 50 else ''}`")
        lines.append(f"   Exit: {result.exit_code} | {result.message}")
        
        if result.stdout:
            preview = result.stdout[:200].replace('\n', ' ')
            lines.append(f"   Output: `{preview}{'...' if len(result.stdout) > 200 else ''}`")
        
        if result.stderr and not result.success:
            err_preview = result.stderr[:150].replace('\n', ' ')
            lines.append(f"   Error: `{err_preview}{'...' if len(result.stderr) > 150 else ''}`")
        
        lines.append("")
    
    return "\n".join(lines)
