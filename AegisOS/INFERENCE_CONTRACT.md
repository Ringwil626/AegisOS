# AegisOS Inference Contract v1.0

**Date:** 2026-02-19  
**Status:** ACTIVE  
**Scope:** Kimi API Integration as Controlled Compute Layer

---

## Executive Summary

This contract defines how Kimi API is integrated into AegisOS as a **stateless, auditable compute device** - not an SDK wrapper or agent framework.

**Core Principle:**
> Kimi is a GPU that speaks JSON. AegisOS controls when, what, and how it's called.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AegisOS Runtime                       │
├─────────────────────────────────────────────────────────┤
│  Supervisor                                              │
│     ↓                                                    │
│  Fetch pending task                                      │
│     ↓                                                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │           InferenceExecutor                        │  │
│  │  ┌─────────────┐    ┌─────────────────────────┐   │  │
│  │  │StateBuilder │ →  │  Construct Prompt       │   │  │
│  │  └─────────────┘    └─────────────────────────┘   │  │
│  │            ↓                                       │  │
│  │  ┌─────────────────────────────────────────────┐   │  │
│  │  │  Check Budget (Phase5 Ledger)               │   │  │
│  │  └─────────────────────────────────────────────┘   │  │
│  │            ↓                                       │  │
│  │  ┌─────────────┐    ┌─────────────────────────┐   │  │
│  │  │kimi_client  │ →  │  Execute Inference      │   │  │
│  │  │(stateless)  │    │  - Retry: 2x            │   │  │
│  │  └─────────────┘    │  - Timeout: enforced    │   │  │
│  │            ↓         └─────────────────────────┘   │  │
│  │  ┌─────────────┐    ┌─────────────────────────┐   │  │
│  │  │Validator    │ →  │  Validate Output        │   │  │
│  │  └─────────────┘    └─────────────────────────┘   │  │
│  │            ↓                                       │  │
│  │  ┌─────────────┐    ┌─────────────────────────┐   │  │
│  │  │UsageLogger  │ →  │  Log to Phase5 Ledger   │   │  │
│  │  └─────────────┘    └─────────────────────────┘   │  │
│  └───────────────────────────────────────────────────┘  │
│     ↓                                                    │
│  Mark task complete                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Module Responsibilities

### 2.1 `infra/kimi_client.py` - Stateless Inference Executor

**Role:** Compute device driver

**Constraints:**
- ✅ Stateless: No internal state between calls
- ✅ Auditable: Returns full usage metrics
- ✅ Interruptible: Enforces timeout at call level
- ✅ Retryable: Exponential backoff
- ✅ Validated: Output structure verification

**Forbidden:**
- ❌ Stream interfaces
- ❌ Session/memory interfaces
- ❌ Agent interfaces
- ❌ Internal caching
- ❌ Task logic generation
- ❌ Direct DB writes

**Only Interface:**
```python
def run_inference(request: InferenceRequest) -> InferenceResult:
    """Send → Wait → Validate → Return structured result"""
```

### 2.2 `core/state_builder.py` - Prompt Construction

**Role:** Context assembler

**Responsibility:**
- Gather project context
- Load agent.md, history/, project_desc.md
- Format user instructions
- Assemble system prompts

**No inference logic** - only text construction.

### 2.3 `core/validator.py` - Output Validation

**Role:** Safety gate

**Responsibility:**
- Validate JSON structure
- Check action schema compliance
- Verify safety constraints
- Path traversal detection

**Fail fast** on invalid outputs.

### 2.4 `audit/usage_logger.py` - Cost Audit

**Role:** Phase5 Ledger integration

**Responsibility:**
- Write usage to `ai_ledger` table
- Calculate estimated costs
- Support rejection/failure logging

**Note:** `kimi_client` is pure - this module handles all DB writes.

---

## 3. Data Structures

### 3.1 Input: InferenceRequest

```python
@dataclass(frozen=True)
class InferenceRequest:
    task_id: str           # Required: For attribution
    project: str           # Required: Cost allocation
    model: str             # Required: Model identifier
    temperature: float     # Required: Sampling temp
    max_tokens: int        # Required: Output limit
    timeout_sec: int       # Required: Hard timeout
    prompt: str            # Required: Complete prompt
    metadata: Dict         # Optional: Audit context
```

**Why metadata?**
- Token cost attribution
- AI self-modification audit
- Discord user responsibility binding

### 3.2 Output: InferenceResult

```python
@dataclass(frozen=True)
class InferenceResult:
    task_id: str           # Mirrors request
    success: bool          # Execution status
    output_text: str       # Raw output
    usage: Dict[str, int]  # Token counts
    latency_ms: int        # Response time
    error: Optional[str]   # Error message
```

**Usage structure (REQUIRED):**
```python
usage = {
    "prompt_tokens": int,
    "completion_tokens": int,
    "total_tokens": int
}
```

**⚠️ CRITICAL:** This is the ONLY source of truth for Phase5 cost auditing.

---

## 4. Execution Strategy

### 4.1 Retry Policy

```python
MAX_RETRY = 2
BACKOFF = exponential (1s → 3s)

Retry on:
- TimeoutError
- 5xx errors

Never retry on:
- 4xx errors
- ValidationError
```

### 4.2 Timeout Enforcement

```python
# Outer timeout (enforced by executor)
if runtime > timeout_sec:
    abort request
    return success=False

# Inner timeout (SDK level)
timeout=timeout_sec - 1
```

**Don't trust SDK timeout alone.**

### 4.3 Response Validation

```python
# Must detect:
- output_text length > 0
- usage.total_tokens > 0
- valid JSON structure
- action schema compliance

# Otherwise: success = False
```

---

## 5. Call Path

```
Supervisor
   ↓
Fetch pending task
   ↓
InferenceExecutor.execute()
   ↓
┌─────────────────────────────────────┐
│ 1. StateBuilder.build_prompt()      │
│    - Gather context                 │
│    - Assemble prompt                │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 2. Budget Check (Phase5)            │
│    - Check daily/hourly limits      │
│    - Reject if over budget          │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 3. kimi_client.run_inference()      │
│    - Stateless execution            │
│    - Retry with backoff             │
│    - Timeout enforcement            │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 4. Validator.validate()             │
│    - JSON parse                     │
│    - Schema check                   │
│    - Safety constraints             │
└─────────────────────────────────────┘
   ↓
┌─────────────────────────────────────┐
│ 5. UsageLogger.log_inference_usage()│
│    - Write to ai_ledger             │
│    - Calculate costs                │
└─────────────────────────────────────┘
   ↓
Mark task complete
```

---

## 6. Governance Compliance

### 6.1 AI Authority Boundaries

| Action | AI Can | AI Cannot |
|--------|--------|-----------|
| Generate code | ✅ | - |
| Write to DB | ❌ | All DB writes via UsageLogger |
| Modify runtime | ❌ | Only through Evolution process |
| Access secrets | ❌ | Env vars handled by Supervisor |
| Control flow | ❌ | Supervisor controls execution |

### 6.2 Self-Evolution Support

This contract enables self-evolution because:

1. **Structured Input/Output** - AI generates code changes as JSON
2. **Staging Area** - Changes go to `evolution/staging/` first
3. **Governance Check** - Validator ensures compliance
4. **Human Approval** - `/approve` required before deployment
5. **Hot Switch** - `/switch` activates new version
6. **Rollback** - Automatic on failure

**CLI cannot do this** - only API + structured output enables it.

---

## 7. Error Handling

### 7.1 Budget Rejection

```python
result = InferenceResult(
    success=False,
    error="BUDGET_REJECTED: Daily limit exceeded",
    usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    ...
)
log_inference_rejection(...)
```

### 7.2 Timeout

```python
result = InferenceResult(
    success=False,
    error="TimeoutError: Inference timed out after 300s",
    usage={"prompt_tokens": X, "completion_tokens": 0, "total_tokens": X},
    ...
)
log_inference_failure(...)
```

### 7.3 Validation Failure

```python
result = InferenceResult(
    success=False,
    error="VALIDATION_FAILED: Missing 'actions' field",
    usage={"prompt_tokens": X, "completion_tokens": Y, "total_tokens": X+Y},
    ...
)
log_inference_failure(...)
```

---

## 8. Migration Guide

### From Old `kimi_client.py`:

```python
# OLD (deprecated):
from aegisos.ai.kimi_client import get_client
client = get_client()
result = client.run_task(prompt, context)

# NEW (Inference Contract):
from aegisos.executor.inference_executor import execute_inference
result = execute_inference(
    task_id="task_001",
    project="my_app",
    instruction="Add login feature",
    file_context={"app.py": "..."}
)

if result.success:
    actions = json.loads(result.output_text)
    # Use actions...
```

---

## 9. Files Reference

| File | Purpose | Contract Role |
|------|---------|---------------|
| `infra/kimi_client.py` | Stateless inference | Compute device |
| `core/state_builder.py` | Prompt construction | Context assembler |
| `core/validator.py` | Output validation | Safety gate |
| `audit/usage_logger.py` | Cost logging | Phase5 integration |
| `executor/inference_executor.py` | Orchestration | Integration layer |

---

## 10. Verification Checklist

Before deploying:

- [ ] `kimi_client.py` has no DB imports
- [ ] `kimi_client.py` has no stream/session interfaces
- [ ] `InferenceRequest` requires `task_id`
- [ ] `InferenceResult` includes `usage` with all token counts
- [ ] Retry policy: 2 retries, exponential backoff
- [ ] Timeout enforced at call level
- [ ] Validator checks all action types
- [ ] UsageLogger writes to `ai_ledger`
- [ ] Budget check before execution
- [ ] All errors return `InferenceResult` (never raise)

---

## 11. Future Evolution

This contract enables:

1. **Model Swapping** - Change model without touching system logic
2. **Multi-Model** - Route different tasks to different models
3. **Token Optimization** - Compress prompts based on usage data
4. **Cost Attribution** - Per-project, per-user cost tracking
5. **Auto-Scaling** - Dynamic timeout/retry based on load

---

**Version:** 1.0  
**Last Updated:** 2026-02-19  
**Owner:** AegisOS Core Team
