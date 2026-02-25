---

AegisOS Governance Document

Version: 1.0
Scope: All developers, AI agents, and runtime components interacting with AegisOS
Purpose: Ensure system stability, auditability, and controlled AI interaction


---

1. Runtime Contract v1.0

1.1 System Role Definition

AegisOS is a deterministic execution runtime supervising AI-assisted change.

It is not an agent framework or planning system.

Responsibilities: accept tasks, validate, execute in sandbox, record outcomes, remain restartable.


1.2 Authority Boundaries

AI cannot mutate system state, DB, task lifecycle, runtime, supervisor behavior, or configuration.

Only approved components may mutate DB:

executor.py → task status

supervisor.py → system_state.status

runtime/manager.py → runtime_version



1.3 Task Lifecycle

Allowed transitions: pending → running → completed|failed

Timeout reset: running → pending only

No other transitions allowed

All transitions managed by Executor only


1.4 Supervisor Responsibilities

Only emits heartbeat

Responds to start/stop

Must not schedule, monitor, or call AI


1.5 Database Source of Truth

DB owns system state; filesystem state is derivative

All actions must be reproducible from DB tables


1.6 Heartbeat Semantics

Heartbeat = process alive only

Must not imply progress, success, or AI health


1.7 AI Interaction

AI output must conform to JSON Action Schema

Invalid output → task failed, no execution


1.8 Execution Sandbox

Executor operates only in /workspace/<project>

Cannot touch core runtime files or system paths

Actions must be deterministic and replayable


1.9 Runtime Switching

Spawn new runtime, verify health, promote atomically

Direct in-place upgrade forbidden

Rollback must always be possible


1.10 Failure Semantics

Heartbeat missing → runtime dead

Task timeout → execution stalled

Schema invalid → AI deviation

Executor crash → task failed

Switch incomplete → dual runtime conflict


1.11 Observability

Must be queryable without logs:

runtime_version, supervisor liveness, pending tasks, running task age, last switch result, AI cost usage



1.12 AI Cost Governance

Log: model, tokens_in, tokens_out, estimated_cost, task_id

No unmetered AI usage


1.13 Determinism

Same DB + same code → identical execution


1.14 Forbidden Drift

No autonomous planning loops, agent frameworks, in-memory orchestration, hidden caches


1.15 Change Control

Modifications to task lifecycle, DB schema, execution boundaries, or runtime rules require contract version increment


1.16 Prime Directive

Always prioritize restartability over autonomy



---

2. Compliance Checklist v1.0

Section 1: Authority enforcement — AI cannot mutate DB or system state

Section 2: Task lifecycle integrity — only allowed state transitions

Section 3: Supervisor dumbness — only heartbeat and start/stop

Section 4: Deterministic execution boundary — workspace only

Section 5: AI output must be structured — validate JSON schema

Section 6: DB is the source of truth — all state recoverable

Section 7: Heartbeat semantics — "alive" only

Section 8: Runtime switching safety — isolated new runtime, atomic promotion

Section 9: Observability — queryable without logs

Section 10: AI cost accounting — log all AI calls

Section 11: Deterministic replay check — same DB → same results

Section 12: Forbidden drift detection — no agent frameworks, background planners, or memory chains for control


> Implementation is compliant only if all sections pass.




---

3. AI Developer Operating Rules v1.0

1. You are writing infrastructure, not an agent. No autonomous loops.


2. Do not move control logic into prompts.


3. DB owns reality. No hidden state or globals.


4. No background magic. All actions must be traceable to DB.


5. Supervisor stays stupid — heartbeat only.


6. AI is a tool, not a brain — validate and discard as needed.


7. All side effects must be auditable — include task_id, timestamp, result.


8. Determinism over performance — no speculative execution.


9. No framework gravity — avoid Celery, LangChain, event buses, DI containers.


10. Task execution must be boring — fetch → validate → execute → record → exit.


11. Version switching must be surgical — spawn, verify, promote, retain rollback.


12. No self-modifying core — AI may modify projects, never runtime.


13. Explain simply — every action must be explainable in 1–2 sentences.


14. Prefer explicit over clever — avoid meta-programming.


15. System must survive crashes — design for abrupt termination.


16. Guard against future AI mistakes — anticipate hallucinations, over-optimizations, generalization errors.




---

4. Operating Mantra

> More explicit, more restartable, more inspectable, less autonomous.



This governance document must remain in root of repository and apply to all future development, including AI-assisted code, runtime changes, and infrastructure modifications.


---
