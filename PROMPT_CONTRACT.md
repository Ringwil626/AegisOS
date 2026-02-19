# AegisOS Prompt Contract v1.0

**Date:** 2026-02-19  
**Status:** ACTIVE  
**Version:** 1.0  
**Purpose:** Machine Contract for AI Inference

---

## Executive Summary

Prompt Contract v1.0 将 AI Prompt 定义为**系统调用协议**，而非聊天消息。

**核心转变：**
- ❌ 从：AI 是助手，可以解释、建议、发挥
- ✅ 到：AI 是执行引擎，只能按 Schema 返回

这让模型像**函数一样工作** —— 输入确定，输出可预测，可被程序直接执行。

---

## 1. Design Philosophy

### 1.1 Deterministic AI Syscall Layer

```
Traditional AI Usage:
  User → Natural Language → AI → Free-form Response → Manual Parse

AegisOS Prompt Contract:
  System → Contract Prompt → AI → Strict JSON → Program Execution
```

**要求：**
- 每次调用可重放
- 每次输出可验证
- 每次失败可回滚

### 1.2 禁止自由语言

| 禁止 | 允许 |
|------|------|
| 解释 | 结构化 JSON |
| 建议 | 确定性执行 |
| 自由发挥 | Schema 约束 |
| 提问 | 成功/失败状态 |

---

## 2. Contract Structure

Prompt **永远由 5 个区块组成**，顺序不可改变：

```
[SYSTEM_ROLE]
[EXECUTION_RULES]
[CONTEXT_STATE]
[TASK_DEFINITION]
[OUTPUT_SCHEMA]
```

### 2.1 [SYSTEM_ROLE]

定义模型身份 —— 不是 AI，是系统组件。

```
[SYSTEM_ROLE]
You are an execution engine inside AegisOS.
You do not explain.
You do not chat.
You do not suggest improvements.
You only produce structured output strictly matching OUTPUT_SCHEMA.
```

### 2.2 [EXECUTION_RULES]

硬约束（防止模型"发挥"）。

```
[EXECUTION_RULES]
Rules:
1. Output must be valid JSON only.
2. No markdown.
3. No commentary.
4. No extra fields.
5. If task cannot be completed, return failure schema.
6. Never ask questions.
7. Never assume missing data.
8. Deterministic execution only.
9. Prompt Version: 1.0
```

### 2.3 [CONTEXT_STATE]

由系统注入当前运行态。

```
[CONTEXT_STATE]
Project: billing_service
Runtime Version: v2
Task ID: task_1832
Environment: staging
Working Directory: /workspace/billing
Prompt Version: 1.0
```

**原则：** 只允许客观状态，不允许描述性语言。

### 2.4 [TASK_DEFINITION]

真正要执行的内容。

```
[TASK_DEFINITION]
Action: create_file

Inputs:
file_path: pricing/calc.py
content: |
  def calculate_price(base, tax_rate):
      return base * (1 + tax_rate)
```

**原则：**
- 必须是结构化 Action + Inputs
- 禁止自然语言任务描述

### 2.5 [OUTPUT_SCHEMA]

**最重要** —— 强制 AI 服从结构。

```
[OUTPUT_SCHEMA]
Return JSON with EXACT structure:

{
  "status": "success | failure",
  "prompt_version": "1.0",
  "artifacts": [
    {
      "type": "file | log | data",
      "path": "string",
      "content": "string"
    }
  ],
  "errors": [
    {
      "code": "string",
      "message": "string"
    }
  ],
  "metrics": {
    "confidence": "high | medium | low"
  }
}
```

---

## 3. Complete Example

### 3.1 Input Prompt

```
[SYSTEM_ROLE]
You are an execution engine inside AegisOS.
You do not explain.
You do not chat.
You do not suggest improvements.
You only produce structured output strictly matching OUTPUT_SCHEMA.

[EXECUTION_RULES]
Rules:
1. Output must be valid JSON only.
2. No markdown.
3. No commentary.
4. No extra fields.
5. If task cannot be completed, return failure schema.
6. Never ask questions.
7. Never assume missing data.
8. Deterministic execution only.
9. Prompt Version: 1.0

[CONTEXT_STATE]
Project: billing_service
Runtime Version: v2
Task ID: task_1832
Environment: staging
Working Directory: /workspace/billing
Prompt Version: 1.0

[TASK_DEFINITION]
Action: create_file

Inputs:
file_path: pricing/calc.py
content: |
  def calculate_price(base, tax_rate):
      return base * (1 + tax_rate)

[OUTPUT_SCHEMA]
Return JSON with EXACT structure:

{
  "status": "success | failure",
  "prompt_version": "1.0",
  "artifacts": [
    {
      "type": "file | log | data",
      "path": "string",
      "content": "string"
    }
  ],
  "errors": [
    {
      "code": "string",
      "message": "string"
    }
  ],
  "metrics": {
    "confidence": "high | medium | low"
  }
}
```

### 3.2 Valid Output (Success)

```json
{
  "status": "success",
  "prompt_version": "1.0",
  "artifacts": [
    {
      "type": "file",
      "path": "pricing/calc.py",
      "content": "def calculate_price(base, tax_rate):\n    return base * (1 + tax_rate)"
    }
  ],
  "errors": [],
  "metrics": {
    "confidence": "high"
  }
}
```

### 3.3 Valid Output (Failure)

```json
{
  "status": "failure",
  "prompt_version": "1.0",
  "artifacts": [],
  "errors": [
    {
      "code": "PATH_EXISTS",
      "message": "File already exists: pricing/calc.py"
    }
  ],
  "metrics": {
    "confidence": "high"
  }
}
```

### 3.4 Invalid Output (Protocol Violation)

```json
{
  "status": "success",
  "output": "I created the file for you.",
  "result": "File created successfully!"
}
```

**Violation:**
- Missing `prompt_version`
- Missing `artifacts` array
- Extra fields: `output`, `result`
- Contains natural language

**Result:** `AI_PROTOCOL_VIOLATION` → Task marked failed

---

## 4. Implementation

### 4.1 State Builder

```python
from aegisos.core.state_builder import PromptContractBuilder, ActionType

builder = PromptContractBuilder(project="billing_service")

prompt = builder.build_contract_prompt(
    task_id="task_1832",
    action=ActionType.CREATE_FILE,
    inputs={
        "file_path": "pricing/calc.py",
        "content": "def calc(): return 42"
    },
    runtime_version="v2",
    environment="staging"
)
```

### 4.2 Validator

```python
from aegisos.core.validator import strict_validate, ProtocolViolation

try:
    data = strict_validate(ai_output)
    # data is guaranteed to match Contract v1.0 schema
    if data["status"] == "success":
        for artifact in data["artifacts"]:
            write_file(artifact["path"], artifact["content"])
    else:
        handle_failure(data["errors"])
except ProtocolViolation as e:
    # AI violated contract - log and fail task
    mark_task_failed(f"AI_PROTOCOL_VIOLATION: {e}")
```

### 4.3 Allowed Actions

| Action | Required Inputs |
|--------|-----------------|
| `create_file` | `file_path`, `content` |
| `modify_file` | `file_path`, `content` or `new_code` |
| `delete_file` | `file_path` |
| `run_test` | `test_command` |
| `analyze_code` | `file_path` |
| `generate_patch` | `target_files` |

---

## 5. Validation Rules

### 5.1 Required Fields

Top-level fields (all required):
- `status`: `"success"` or `"failure"`
- `prompt_version`: `"1.0"`
- `artifacts`: Array of artifact objects
- `errors`: Array of error objects (empty on success)
- `metrics`: Object with `confidence` field

### 5.2 Artifact Schema

Each artifact must have exactly:
```json
{
  "type": "file | log | data",
  "path": "string",
  "content": "string"
}
```

### 5.3 Error Schema

Each error must have exactly:
```json
{
  "code": "string",
  "message": "string"
}
```

### 5.4 No Extra Fields

Any field not in schema = `EXTRA_FIELDS` violation.

---

## 6. Versioning

### 6.1 Prompt Version

Current: `PROMPT_VERSION = "1.0"`

- Hardcoded in `state_builder.py`
- Injected into every prompt
- Validated in every output

### 6.2 Future Versions

When upgrading:
1. Create `PROMPT_VERSION = "2.0"`
2. Update schema in `OUTPUT_SCHEMA` block
3. Update validator rules
4. Maintain backward compatibility for task replay

### 6.3 Historical Tasks

Task records store prompt version:
```sql
SELECT prompt_version FROM tasks WHERE id = ?
```

Allows replay with correct contract version.

---

## 7. Governance

### 7.1 AI Authority Boundaries

| AI Can | AI Cannot |
|--------|-----------|
| Return structured JSON | Explain reasoning |
| Create/modify/delete files | Suggest improvements |
| Run tests | Ask questions |
| Report failures | Assume missing data |

### 7.2 Protocol Violations

When AI violates contract:
1. Task immediately marked failed
2. Error logged: `AI_PROTOCOL_VIOLATION`
3. Human review required
4. AI may be prompted to retry with stricter instructions

### 7.3 Safety

- Path traversal blocked
- Dangerous commands blocked
- All file operations within project directory
- No network access from AI output

---

## 8. Benefits

| Capability | Enabled By |
|------------|------------|
| Reproducibility | Deterministic prompt structure |
| Verifiability | Strict schema validation |
| Rollback | Structured artifacts enable undo |
| Versioning | Prompt version tracking |
| Audit | Every action logged with structure |
| Self-evolution | AI can modify code → validate → deploy |

---

## 9. Files Reference

| File | Purpose |
|------|---------|
| `core/state_builder.py` | Build Contract Prompts |
| `core/validator.py` | Validate Contract outputs |
| `PROMPT_CONTRACT.md` | This document |

---

## 10. Quick Reference

### Building Prompt
```python
from aegisos.core.state_builder import build_contract_prompt

prompt = build_contract_prompt(
    project="my_app",
    task_id="task_001",
    action="create_file",
    inputs={"file_path": "main.py", "content": "..."}
)
```

### Validating Output
```python
from aegisos.core.validator import validate_ai_output

is_valid, error, data = validate_ai_output(ai_response)
if not is_valid:
    print(f"Protocol violation: {error}")
```

### Strict Validation
```python
from aegisos.core.validator import strict_validate

try:
    data = strict_validate(ai_response)
    # Guaranteed Contract v1.0 compliant
except ProtocolViolation as e:
    handle_violation(e)
```

---

**Version:** 1.0  
**Last Updated:** 2026-02-19  
**Owner:** AegisOS Core Team
