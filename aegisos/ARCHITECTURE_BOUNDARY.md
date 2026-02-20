# AegisOS Architecture Boundary

## Runtime-First Architecture Definition

AegisOS is a **deterministic runtime**, not an agent framework.

---

## Layer Definitions

### LAYER 1 — CORE RUNTIME
**Path**: `aegisos/core/`

**Components**:
- supervisor - Process lifecycle controller
- executor - Task state machine driver
- state - State management
- db - SQLite persistence

**Rules**:
- NO AI ALLOWED
- NO import from intelligence/analysis/memory/ai
- Deterministic only
- Must be replayable, auditable, recoverable

---

### LAYER 2 — EXECUTION
**Path**: `aegisos/executor/`

**Components**:
- task_runner - Task execution wrapper
- inference_executor - SINGLE AI call gate
- worker - Worker pool (moved from core)
- action_executor - Action execution

**Rules**:
- AI allowed ONLY as tool
- All AI calls MUST go through inference_executor
- No direct OpenAI/Kimi client creation

---

### LAYER 3 — INTERFACE
**Path**: `aegisos/interfaces/`

**Components**:
- discord - Discord bot interface
- cli - Command line interface

**Rules**:
- Read-only access to state
- Commands enqueue tasks, never execute directly
- No AI logic

---

### LAYER 4 — GOVERNANCE
**Path**: `aegisos/governance/`

**Components**:
- Proposal system
- Review system
- Approval workflow

**Rules**:
- Human-approved change system ONLY
- NEVER auto-triggered by Supervisor
- ONLY accessible via Discord commands (/propose, /apply)

---

### LAYER 5 — PROJECT SPACE
**Path**: `projects/`

**Components**:
- `_aegisos_internal_tools/` - Offline AI tools
  - intelligence/ - Moved from aegisos/
  - analysis/ - Moved from aegisos/
  - memory/ - Moved from aegisos/

**Rules**:
- ALL intelligence lives here
- NOT loaded at runtime startup
- Optional tools, not core OS

---

## Enforcement

### Import Rules

```python
# LAYER 1 (core) CAN import:
from aegisos.db import ...
from aegisos.core import ...

# LAYER 1 CANNOT import:
from aegisos.intelligence import ...  # FORBIDDEN
from aegisos.analysis import ...      # FORBIDDEN
from aegisos.memory import ...        # FORBIDDEN
from aegisos.ai import ...            # FORBIDDEN
```

### AI Call Gate

```python
# ONLY inference_executor can:
from openai import OpenAI
# or
import requests  # to AI API

# ALL other modules MUST use:
from aegisos.executor.inference_executor import run_inference
```

---

## Semantic Rules

### Forbidden Terms in Core
- "self-evolve"
- "auto evolve"
- "automatic upgrade"
- "learn from"
- "adapt to"

### Required Terms
- "proposal" - Human-created change request
- "review" - Human evaluation
- "apply_with_approval" - Human-triggered execution

---

## Runtime Protection

Supervisor startup asserts (in supervisor.py):

```python
FORBIDDEN = ["intelligence", "analysis", "memory"]
for m in sys.modules:
    for f in FORBIDDEN:
        assert f not in m, f"Forbidden module loaded: {m}"
```

---

## Change Control

Any modification to this architecture requires:
1. Human approval
2. Review of all import changes
3. Verification of layer boundaries
4. Runtime protection test

---

**Version**: 1.0  
**Last Updated**: 2026-02-19  
**Enforcement**: STRICT
