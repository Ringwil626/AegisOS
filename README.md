# AegisOS

**A Deterministic Execution OS with an Attached Reasoning Engine**

[![Status](https://img.shields.io/badge/status-production%20hardened-green)]()

AegisOS is an operating system for managing AI-assisted tasks with strict guarantees: deterministic, auditable, budget-enforced, human-governed, and recoverable.

> **Not an AI Agent. Not a Self-Evolving System.** An OS where AI is a callable tool, not the controller.

---

## Quick Start

```bash
# 1. Install (only required dependency)
pip install pyyaml

# 2. Run (mock AI mode)
python main.py

# 3. (Optional) Enable Discord and real AI
export DISCORD_TOKEN="your-token"
export MOONSHOT_API_KEY="sk-your-key"
python main.py
```

Expected startup:
```
[GUARD] Runtime Write Firewall: ACTIVE
[GUARD] Level0 tables protected: 6
[OK] System initialized.
```

---

## What Makes AegisOS Different

| Feature | AegisOS | Traditional AI Agent |
|---------|---------|---------------------|
| State Source | SQLite (ground truth) | AI reasoning (derived) |
| AI Role | Callable tool | Controller |
| Evolution | Human-approved only | Auto-evolution |
| Budget | Hard enforced | Soft limits |
| Recovery | Deterministic | State loss risk |

---

## Architecture

```
Layer 1 — Core Runtime (supervisor, executor, db)
    ↓
Layer 2 — Execution (inference_executor - SINGLE AI GATE)
    ↓
Layer 3 — Interface (Discord)
    ↓
Layer 4 — Governance (human-approved changes)
    ↓
Layer 5 — Project Space (user code)
```

**Key**: AI can only call through Layer 2. Never touches Layer 1 directly.

---

## Documentation

| Document | Purpose |
|----------|---------|
| [USAGE.md](USAGE.md) | Quick start, commands, troubleshooting |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, layer partition, DB firewall |
| [CONTRACTS.md](CONTRACTS.md) | Executor, Inference, Prompt contracts |

---

## Core Guarantees

1. **Deterministic** - Same SQLite state → Same behavior
2. **Auditable** - All changes in `usage_ledger`, `tasks`, `heartbeats`
3. **Budget-Enforced** - AI cannot bypass spending limits
4. **Human-Governed** - `/propose` → review → `/approve` → apply
5. **Recoverable** - Stop/start preserves exact state

---

## Key Design: DB Write Firewall

```python
# AI trying to write directly → BLOCKED
aegisos.intelligence.* → UPDATE tasks → ❌ RuntimeWriteViolation

# Only allowed path
AI → proposal → human /approve → RuntimeWriter → UPDATE tasks → ✅
```

**6 Level-0 tables protected**: `tasks`, `system_state`, `heartbeats`, `usage_ledger`, `budgets`, `rate_limit_log`

---

## Usage Example

```bash
# Discord commands
/task create ai "Review src/main.py"
/status
/usage
/propose "Optimize prompt templates"
/approve 123
```

---

## System Requirements

- Python 3.11+
- SQLite3
- 1 dependency: `pyyaml`
- Optional: `discord.py`, `openai`

---

## License

MIT License

---

**AegisOS**: SQLite is ground truth. AI is callable. Human governs evolution.
