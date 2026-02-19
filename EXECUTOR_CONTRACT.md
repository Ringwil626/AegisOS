# AegisOS Executor Contract v1.0

**Date:** 2026-02-19  
**Status:** ACTIVE  
**Version:** 1.0  
**Purpose:** Task State Machine Driver Specification

---

## Executive Summary

Executor Contract v1.0 将 Executor 从"AI 调用器"转变为**任务状态机执行器**。

**核心转变：**
- ❌ 从：智能执行器，做决策、重试、处理异常
- ✅ 到：确定性状态机驱动器，严格按规则推进状态

**设计目标：**
- 可恢复（超时回收）
- 可审计（完整执行日志）
- 可回滚（严格状态机）
- 可升级（短生命周期）

---

## 1. Architecture

### 1.1 Three-Layer Isolation

```
┌─────────────────────────────────────────────────────────┐
│  Supervisor (Lifecycle Controller)                      │
│  - Only loop in system                                  │
│  - Emits heartbeats                                     │
│  - Calls execute_one_task()                             │
│  - Knows NOTHING about AI                               │
├─────────────────────────────────────────────────────────┤
│  Executor (State Machine Driver)                        │
│  - Claims one task                                      │
│  - Executes via Prompt Contract                         │
│  - Advances state                                       │
│  - Returns result                                       │
│  - Short lifecycle (no while True)                      │
├─────────────────────────────────────────────────────────┤
│  AI (Untrusted Compute Node)                            │
│  - Stateless inference                                  │
│  - Returns structured output                            │
│  - No system knowledge                                  │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Why This Separation?

| Layer | Responsibility | Why Separate? |
|-------|---------------|---------------|
| Supervisor | Lifecycle control | Can restart/upgrade without losing tasks |
| Executor | State machine | Deterministic, testable, no intelligence |
| AI | Compute | Untrusted, replaceable, stateless |

**Most AI Agent systems fail because they mix these layers.**

---

## 2. Task State Machine

### 2.1 States

```
pending → running → completed
               ↘
                failed
```

**禁止的状态：**
- ❌ `retrying` - Use new task instead
- ❌ `waiting_ai` - No partial states
- ❌ `thinking` - No AI states visible
- ❌ `partial_done` - Binary completion

### 2.2 State Transitions

| From | To | Valid | Trigger |
|------|-----|-------|---------|
| pending | running | ✅ | Executor claims task |
| running | completed | ✅ | Execution success |
| running | failed | ✅ | Any failure |
| pending | completed | ❌ | Must go through running |
| completed | pending | ❌ | Terminal state |
| failed | running | ❌ | New task required |

### 2.3 Strict Success Criteria

Task is `completed` **ONLY IF**:
1. `inference_success == True` (AI returned valid response)
2. `schema_valid == True` (Output matches Prompt Contract)
3. `artifacts_applied_without_error == True` (Files written)

**否则一律 `failed`。**

---

## 3. Execution Flow

### 3.1 Step-by-Step

```
Step 1: Cleanup stuck tasks
        Reset running tasks > timeout to pending
        
Step 2: Claim pending task
        SELECT ... ORDER BY id ASC LIMIT 1
        UPDATE status = 'running', started_at = now
        
Step 3: Build Prompt Contract
        state_builder.build_contract_prompt()
        
Step 4: Run inference
        kimi_client.run_inference()
        
Step 5: Validate output
        validator.strict_validate()
        
Step 6: Apply artifacts
        ArtifactApplier (mechanical only)
        
Step 7a: Mark completed
         If all checks pass
         
Step 7b: Mark failed
         If any step fails
```

### 3.2 Failure Handling

**Any step fails → immediate failed state**

- No retry within same task
- No "continue anyway"
- No partial success

**Retry must be new task.**

---

## 4. Concurrency Control

### 4.1 Task Claiming (Anti-Race)

```sql
-- Atomic claim operation
UPDATE tasks 
SET status = 'running', 
    started_at = unixepoch()
WHERE id = (
    SELECT id FROM tasks 
    WHERE status = 'pending' 
    ORDER BY id ASC 
    LIMIT 1
)
RETURNING id, type, status, payload, ...
```

**Key:** Single atomic UPDATE-SELECT prevents multiple Executors claiming same task.

### 4.2 SQLite Limitations

SQLite doesn't support `FOR UPDATE`, but we use:
1. `EXCLUSIVE` transaction isolation
2. Atomic UPDATE with subquery
3. Single-row RETURNING

---

## 5. Timeout Recovery

### 5.1 Problem

Executor/AI/Process/Machine may die while task is `running`.

### 5.2 Solution

**Startup Cleanup:**
```python
def cleanup_stuck_tasks():
    UPDATE tasks
    SET status = 'pending', started_at = NULL
    WHERE status = 'running'
      AND started_at < now - TIMEOUT_WINDOW
```

**Default:** `TIMEOUT_WINDOW = 300 seconds` (5 minutes)

### 5.3 Why Reset to Pending?

- Allows automatic retry
- No manual intervention needed
- System self-heals

---

## 6. Artifact Application

### 6.1 Mechanical Only

Executor **does NOT understand content**.

| Artifact Type | Action |
|---------------|--------|
| `file` | Overwrite write |
| `log` | Append to file |
| `data` | Write JSON |

### 6.2 Security

- Path traversal blocked
- Must be within project directory
- Parent directories auto-created

---

## 7. Audit Trail

### 7.1 Execution Log

Every execution writes to `execution_log`:

```sql
CREATE TABLE execution_log (
    id INTEGER PRIMARY KEY,
    task_id INTEGER NOT NULL,
    started_at INTEGER NOT NULL,
    finished_at INTEGER NOT NULL,
    success BOOLEAN NOT NULL,
    tokens_used INTEGER,
    latency_ms INTEGER,
    error TEXT,
    created_at INTEGER DEFAULT (unixepoch())
);
```

### 7.2 Usage

- Phase5 cost analysis
- Performance monitoring
- Governance decisions
- Auto-downgrade triggers

---

## 8. Implementation

### 8.1 Core Classes

```python
class ContractExecutor:
    """Executor Contract v1.0 implementation."""
    
    def cleanup_stuck_tasks(self) -> int:
        """Reset timed-out tasks to pending."""
        
    def execute_one_task(self) -> Optional[ExecutionResult]:
        """Execute single task (short lifecycle)."""
```

### 8.2 Convenience Function

```python
def execute_one_task(project: str = "default") -> Optional[ExecutionResult]:
    """One-shot task execution."""
```

### 8.3 Supervisor Integration

```python
# In Supervisor._loop():
if status == "running":
    had_task = _execute_task_cycle()
    
def _execute_task_cycle():
    result = execute_one_task(project="default")
    if result:
        print(f"Task #{result.task_id} {result.status.value}")
```

---

## 9. Usage Examples

### 9.1 Execute One Task

```python
from aegisos.core.executor import execute_one_task

result = execute_one_task(project="my_app")

if result:
    print(f"Task {result.task_id}: {result.status.value}")
    print(f"Tokens: {result.tokens_used}")
    print(f"Latency: {result.latency_ms}ms")
else:
    print("No pending tasks")
```

### 9.2 Get Execution Stats

```python
from aegisos.core.executor import get_execution_stats

stats = get_execution_stats(task_id=123)
print(f"Task executed {stats['execution_count']} times")
for exec in stats['executions']:
    print(f"  Success: {exec['success']}, Tokens: {exec['tokens_used']}")
```

### 9.3 Manual Executor (Testing)

```python
from aegisos.core.executor import ContractExecutor

executor = ContractExecutor(project="my_app")

# Cleanup stuck tasks
reset_count = executor.cleanup_stuck_tasks()
print(f"Reset {reset_count} stuck tasks")

# Execute one task
result = executor.execute_one_task()
if result:
    print(f"Result: {result}")
```

---

## 10. Governance

### 10.1 Executor Constraints

| Constraint | Implementation |
|------------|----------------|
| No intelligence | Pure state machine |
| No retry | New task for retry |
| No while True | Single execution |
| No AI knowledge | Just calls client |
| Deterministic | Same input → same state transitions |

### 10.2 Supervisor Constraints

| Constraint | Implementation |
|------------|----------------|
| Only loop | While True here only |
| No AI knowledge | Calls Executor, not AI |
| Lifecycle control | Start/stop/status |
| Heartbeat | Health monitoring |

### 10.3 AI Constraints

| Constraint | Implementation |
|------------|----------------|
| Stateless | No memory between calls |
| Structured output | Contract v1.0 schema |
| No system knowledge | Only sees Prompt |
| Replaceable | Can swap models |

---

## 11. Failure Modes

### 11.1 Executor Failure

| Scenario | Result | Recovery |
|----------|--------|----------|
| Task claim fails | Returns None | Supervisor tries next cycle |
| AI timeout | Task marked failed | Manual retry as new task |
| Schema invalid | Task marked failed | Human review |
| Artifact write fails | Task marked failed | Check permissions |
| DB unavailable | Exception raised | Supervisor logs error |

### 11.2 System Failure

| Scenario | Result | Recovery |
|----------|--------|----------|
| Process killed mid-task | Task stuck in running | Timeout recovery on restart |
| Machine crash | Task stuck in running | Timeout recovery on restart |
| DB corruption | Execution fails | Restore from backup |

---

## 12. Files Reference

| File | Purpose |
|------|---------|
| `core/executor.py` | Executor Contract implementation |
| `core/supervisor.py` | Lifecycle controller |
| `db/sqlite_store.py` | Task state management |
| `EXECUTOR_CONTRACT.md` | This document |

---

## 13. Quick Reference

### State Machine
```
pending → running → completed
               ↘
                failed
```

### Execution Steps
```
1. Cleanup stuck tasks
2. Claim pending task
3. Build Prompt Contract
4. Run inference
5. Validate output
6. Apply artifacts
7. Mark completed/failed
```

### Success Criteria
```python
inference_success and schema_valid and artifacts_applied
```

---

**Version:** 1.0  
**Last Updated:** 2026-02-19  
**Owner:** AegisOS Core Team
