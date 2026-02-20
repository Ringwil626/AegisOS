# AegisOS Contracts

**Version**: 1.0  
**Date**: 2026-02-19

---

## 1. Executor Contract v1.0

### Responsibilities
1. Budget gate check (Phase5) - BEFORE calling AI
2. Claim one pending task from SQLite (atomic)
3. Execute via Prompt Contract
4. Calculate cost immediately (deterministic)
5. Record to usage_ledger (Single Source of Truth)
6. Advance task state based on result

### State Machine
```
pending → running → completed
           ↘
            failed
```

### API

```python
class Executor:
    def execute_one_task(self) -> Optional[ExecutionResult]
        # 1. Cleanup zombie tasks (timeout recovery)
        # 2. Claim one pending task (FOR UPDATE)
        # 3. Build prompt via state_builder
        # 4. Check budget gate
        # 5. Run inference via inference_executor
        # 6. Validate output schema
        # 7. Apply artifacts (file writes)
        # 8. Record usage
        # 9. Mark completed or failed
```

### Timeout Recovery
- Default timeout: 300 seconds
- Executor resets stuck tasks automatically
- Claims are atomic (prevents double execution)

---

## 2. Inference Contract v1.0

### Interface

```python
@dataclass(frozen=True)
class InferenceRequest:
    task_id: str
    project: str
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: int
    prompt: str

@dataclass(frozen=True)
class InferenceResult:
    task_id: str
    success: bool
    output_text: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    latency_ms: int
    error: Optional[str]
```

### Retry Policy
- Max 2 retries
- Exponential backoff (1s → 3s)
- Only on timeout/5xx errors
- 4xx errors fail immediately (don't retry bad requests)

### Usage Contract
- Must return `usage` dict with all token counts
- Must record to `usage_ledger` after call
- Must check budget before call

### Single Entry Point

```python
# ONLY way to call AI
from aegisos.executor.inference_executor import run_inference

# Forbidden:
# - Direct OpenAI client creation
# - Direct HTTP calls to AI API
# - Caching responses
```

---

## 3. Prompt Contract v1.0

### 5-Block Structure

```
[SYSTEM_ROLE]
Execution engine identity

[EXECUTION_RULES]
Hard constraints:
- No explanation
- No chat
- No markdown outside code blocks

[CONTEXT_STATE]
Objective state:
- Project path
- Runtime version
- Environment

[TASK_DEFINITION]
Structured Action + Inputs

[OUTPUT_SCHEMA]
Mandatory JSON structure
```

### Action Types

```python
class ActionType(Enum):
    CREATE_FILE = "create_file"
    MODIFY_FILE = "modify_file"
    DELETE_FILE = "delete_file"
    RUN_TEST = "run_test"
    ANALYZE_CODE = "analyze_code"
    GENERATE_PATCH = "generate_patch"
```

### Output Schema (Strict)

```json
{
    "status": "success|error",
    "action": "action_type",
    "result": {
        "files_created": [...],
        "files_modified": [...],
        "output": "..."
    },
    "error": null
}
```

### Schema Validation
- Strict JSON parsing
- Required fields check
- Type validation
- Unknown fields rejected

---

## Contract Compliance

### For Developers

1. **Always use contracts** - Never bypass
2. **Validate inputs** - Strict schema
3. **Record everything** - Usage, errors, results
4. **Handle timeouts** - Graceful degradation
5. **No silent failures** - Log all errors

### For AI Integration

1. **Prompt Contract** - Build prompts via state_builder
2. **Inference Contract** - Call via inference_executor
3. **Executor Contract** - Let executor manage task lifecycle

---

**Violation**: Any code bypassing contracts will be rejected by CI
