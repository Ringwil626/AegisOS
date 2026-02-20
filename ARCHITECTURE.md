# AegisOS Architecture

**Version**: 1.0 Production  
**Date**: 2026-02-19

---

## Overview

> **AegisOS is a Deterministic Execution OS with an Attached Reasoning Engine.**

Not an AI Agent. Not a Self-Evolving System. An operating system that manages AI-assisted tasks with strict guarantees.

### Core Guarantees

- ✅ **Deterministic** - Same SQLite state → Same behavior
- ✅ **Auditable** - All changes recorded
- ✅ **Budget-Enforced** - AI cannot overspend
- ✅ **Human-Governed** - No auto-evolution
- ✅ **Recoverable** - Stop/start without data loss

---

## 5-Layer Architecture

```
┌─────────────────────────────────────────┐
│  LAYER 5 — PROJECT SPACE                │
│  /projects/*                            │
│  User code, offline AI tools            │
└─────────────────────────────────────────┘
                    │ calls via executor
┌─────────────────────────────────────────┐
│  LAYER 4 — GOVERNANCE                   │
│  Human-approved changes only            │
│  /propose → review → /apply             │
└─────────────────────────────────────────┘
                    │ human approval
┌─────────────────────────────────────────┐
│  LAYER 3 — INTERFACE                    │
│  Discord bot, CLI                       │
│  Enqueues tasks, never executes         │
└─────────────────────────────────────────┘
                    │ enqueue
┌─────────────────────────────────────────┐
│  LAYER 2 — EXECUTION                    │
│  task_runner, inference_executor        │
│  AI allowed ONLY through executor       │
└─────────────────────────────────────────┘
                    │ supervised
┌─────────────────────────────────────────┐
│  LAYER 1 — CORE RUNTIME                 │
│  supervisor, executor, db               │
│  NO AI ALLOWED                          │
└─────────────────────────────────────────┘
                    │ writes
┌─────────────────────────────────────────┐
│  DATABASE — Layer Partitioned           │
│  SQLite with write firewall             │
└─────────────────────────────────────────┘
```

---

## Database Layer Partition

### Level 0 — Runtime Authority (AI Cannot Write)

| Table | Purpose |
|-------|---------|
| `tasks` | Task lifecycle - current worldline |
| `system_state` | System status and versions |
| `heartbeats` | Component health monitoring |
| `usage_ledger` | Token/cost accounting |
| `budgets` | Budget limits and enforcement |
| `rate_limit_log` | Rate limiting audit |

**Access**: Only `aegisos.core.*`, `aegisos.db.runtime_writer`

### Level 1 — Governance (Runtime Cannot Auto-Write)

| Table | Purpose |
|-------|---------|
| `proposals` | Human-reviewed change proposals |
| `strategy_versions` | Approved strategy versions |
| `shadow_runs` | Shadow test results (isolated) |

**Access**: Discord `/propose`, explicit human approval

---

## DB Write Firewall (Hard Constraint)

### Rule

```python
LEVEL_0_TABLES = {
    'tasks', 'system_state', 'heartbeats', 
    'usage_ledger', 'budgets', 'rate_limit_log'
}

FORBIDDEN_CALLERS = {
    'aegisos.ai',
    'aegisos.intelligence',
    'aegisos.memory',
    'aegisos.evolution',
    'aegisos.analysis',
}

# AI trying to write Level 0 → BLOCKED
```

### Error Message

```
RuntimeWriteViolation:
  Module: aegisos.intelligence.optimizer
  Attempted: WRITE to Level 0 table 'tasks'
  Rule: AI-originated code cannot mutate runtime state.
  Action: Submit a proposal via Governance API instead.
```

### Startup Verification

```
[GUARD] Runtime Write Firewall: ACTIVE
[GUARD] Level0 tables protected: 6
[GUARD] Unauthorized writers: BLOCKED
```

---

## AI Modification Path

```
AI → Generate proposal.md
  → Write to proposals table (Governance Layer)
  → Wait for human /approve
  → Supervisor triggers migration_executor
  → RuntimeWriter implements change
```

AI is **NEVER** allowed to:
- Direct `UPDATE tasks`
- Direct modify `budgets`
- Direct write `usage_ledger`

---

## File Structure

```
AegisOS/
├── aegisos/
│   ├── core/                    # Layer 1: Runtime
│   │   ├── supervisor.py
│   │   ├── executor.py
│   │   └── ...
│   ├── executor/                # Layer 2: Execution
│   │   ├── inference_executor.py    # SINGLE AI GATE
│   │   ├── task_runner.py
│   │   └── worker.py
│   ├── db/                      # Persistence + Firewall
│   │   ├── runtime_writer.py    # ONLY write gateway
│   │   ├── sqlite_store.py      # Firewall core
│   │   └── init_all.py
│   ├── governance/              # Layer 4: Human-approved
│   └── interfaces/              # Layer 3: Discord
├── projects/                    # Layer 5: User space
│   └── _aegisos_internal_tools/ # Offline AI tools
├── main.py                      # Entry point
├── config.yaml                  # Configuration
└── requirements.txt             # Dependencies
```

---

## Key Principles

1. **SQLite is Ground Truth** - Not derived from AI reasoning
2. **AI is Callable Tool** - Not controlling
3. **Human Governs Evolution** - No auto-mutation
4. **Layer Partition Enforced** - Runtime vs Governance isolated
5. **Deterministic Recovery** - Stop/start preserves exact state

---

## Future Allowed Changes

✅ **Allowed**:
- New Executors (new AI models)
- New Governance Policies (human-defined)
- New Project Integration
- Optimization (faster, more reliable)

❌ **Forbidden**:
- Auto-Evolution
- AI in Core
- Auto-Approval
- Direct AI→DB writes
- New "Intelligence" Layers

---

**Enforcement**: STRICT  
**Review**: Required for DB/Core changes  
**Audit**: Runtime guard assertions active
