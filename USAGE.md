# AegisOS Usage Guide

**Version**: 1.0  
**Date**: 2026-02-19

---

## Quick Start

### 1. Install Dependencies

```bash
cd AegisOS
pip install pyyaml
```

Optional (for full features):
```bash
pip install discord.py openai  # For Discord bot and real AI
```

### 2. Configure

Edit `config.yaml`:
```yaml
discord:
  token: ""  # Set via DISCORD_TOKEN env var
  admin_users:
    - "YOUR_DISCORD_USER_ID"
```

### 3. Run

```bash
# Basic (mock AI mode)
python main.py

# With Discord
export DISCORD_TOKEN="your-token"
python main.py

# With real AI
export MOONSHOT_API_KEY="sk-your-key"
python main.py
```

Expected output:
```
[GUARD] Runtime Write Firewall: ACTIVE
[GUARD] Level0 tables protected: 6
[OK] System initialized.
[OK] Starting Main Loop...
[OK] Starting Discord bot...
```

---

## Discord Commands

### System Control

| Command | Description |
|---------|-------------|
| `/status` | Show system health |
| `/start` | Start task processing |
| `/stop` | Stop (graceful shutdown) |
| `/usage` | Show token/cost usage |

### Task Management

| Command | Description |
|---------|-------------|
| `/task create <type> <payload>` | Create new task |
| `/task list` | List pending tasks |
| `/task status <id>` | Check task status |

### Governance (Human Approval)

| Command | Description |
|---------|-------------|
| `/propose <change>` | Submit change proposal |
| `/proposals list` | List pending proposals |
| `/approve <id>` | Approve proposal |
| `/apply <id>` | Apply approved change |

---

## Task Types

### AI Task
```
/task create ai "Review code in src/main.py"
```

### Command Task
```
/task create command "npm test"
```

### Custom Task
```json
{
  "type": "custom",
  "payload": {
    "action": "analyze",
    "target": "project_x"
  }
}
```

---

## Budget Management

### Check Budget
```
/usage
```

Output:
```
Project: default
Daily Tokens: 45,230 / 100,000 (45%)
Daily Cost: $2.15 / $5.00 (43%)
Tasks Today: 12
```

### Set Budget (Admin)
```
/budget set <project> <daily_tokens> <daily_cost>
```

### Budget Gates
- **Warning**: 80% of budget
- **Critical**: 95% of budget
- **Hard Stop**: 100% of budget (configurable)

---

## Governance Workflow

### 1. AI Proposes Change
```
[AI Analysis] Token usage increased 30%
[Proposal] Optimize prompt templates
```

### 2. Human Reviews
```
/proposals list
→ Proposal #123: Optimize prompts (High impact, Low risk)
```

### 3. Human Approves
```
/approve 123
```

### 4. System Applies
```
[Applied] Proposal #123
[Shadow] Running 10 tests...
[Result] Token usage reduced 25%
[Active] New prompt template deployed
```

---

## Troubleshooting

### System Won't Start
```bash
# Check if another instance is running
ps aux | grep "python main.py"

# Remove lock file if stale
rm aegisos.lock
```

### Database Locked
```bash
# SQLite WAL mode handles this automatically
# If stuck, restart:
killall python
rm aegisos.db-shm aegisos.db-wal
python main.py
```

### Budget Exceeded
```
[ERROR] BUDGET_EXCEEDED: Daily cost limit reached
```

Solutions:
1. Wait for next day (resets at midnight)
2. Increase budget: `/budget set default 200000 10.0`
3. Check usage: `/usage`

---

## Advanced Configuration

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DISCORD_TOKEN` | Discord bot token | No |
| `MOONSHOT_API_KEY` | Real AI API | No |
| `AEGISOS_DB` | Custom DB path | No |

### Config File

```yaml
# config.yaml
discord:
  token: ""  # From env var DISCORD_TOKEN
  admin_users:
    - "123456789"
  channels:
    system_status: "CHANNEL_ID"
    task_status: "CHANNEL_ID"

quota:
  total_weekly_tokens: 2048000
  warning_threshold: 0.8
  critical_threshold: 0.95

supervisor:
  check_interval: 5
  heartbeat_timeout: 60
```

---

## Backup & Recovery

### Backup Database
```bash
cp aegisos.db aegisos.db.backup.$(date +%Y%m%d)
```

### Restore
```bash
# Stop system
Ctrl+C

# Restore
mv aegisos.db.backup.20240219 aegisos.db

# Restart
python main.py
```

### Recovery Mode
System automatically detects unclean shutdown:
```
[P0-3] Detected unclean shutdown: interrupted
[P0-3] Recovering pending tasks...
[OK] State restored
```

---

## Monitoring

### Health Check
```bash
# View heartbeats
sqlite3 aegisos.db "SELECT component, message, timestamp FROM heartbeats ORDER BY timestamp DESC LIMIT 10;"
```

### Task Status
```bash
# Pending tasks
sqlite3 aegisos.db "SELECT id, type, status FROM tasks WHERE status='pending';"

# Failed tasks
sqlite3 aegisos.db "SELECT id, type, status FROM tasks WHERE status='failed';"
```

### Usage Report
```bash
# Today's usage
sqlite3 aegisos.db "SELECT SUM(tokens_total), SUM(cost_estimate) FROM usage_ledger WHERE created_at > datetime('now', 'start of day');"
```

---

## Development

### Add New Task Type
1. Define in `aegisos/core/state_builder.py`
2. Add handler in `aegisos/executor/task_runner.py`
3. Update Discord commands

### Add New Model
1. Create provider in `aegisos/executor/`
2. Register in `inference_executor.py`
3. Update pricing in `aegisos/db/pricing.py`

---

**Need Help?** Check `ARCHITECTURE.md` for system design.
