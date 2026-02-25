# AegisOS 运维操作手册 (Runbook)

**版本**: Phase 5 + Phase 6  
**最后更新**: 2026-02-17  
**适用对象**: 系统管理员 / AI 治理负责人

---

## 1. 系统架构概览

### 1.1 核心组件

| 组件 | 职责 | 关键约束 |
|------|------|----------|
| **Supervisor** | 生命维持，心跳 emitting | 永不接触 tasks/ledger |
| **Main Loop** | 执行门控 (Gate) | 唯一调度点，10s tick |
| **Executor** | 任务执行 | 被动工具，不感知状态 |
| **AI Ledger** | 成本审计 | 所有 AI 调用必须记录 |
| **Evolution Manager** | 进化提案生成 | 只写 proposals/，不碰 runtime |
| **Validator** | 提案验证 | 零 AI 消耗，纯测试 |

### 1.2 状态机

```
System State:
  initialized → running ↔ stopped
  
Task State:
  pending → running → completed/failed
  
Evolution State:
  proposed → validated → approved → deployed
       ↓
     rejected
```

### 1.3 关键文件位置

```
aegisos/
├── core/supervisor.py      # 心跳组件
├── db/sqlite_store.py      # 数据库层
├── executor/task_runner.py # 任务执行
├── ai/ledger.py            # AI 成本审计
├── evolution/manager.py    # 进化管理
├── evolution/validator.py  # 验证器
└── evolution/proposals/    # 提案存储（隔离区）

aegisos.db                  # SQLite 数据库
```

---

## 2. 启动与停止

### 2.1 启动系统

```bash
# 设置 Discord Token
$env:DISCORD_TOKEN="your-token-here"

# 启动系统
python main.py
```

**启动日志检查**:
```
Initializing database...           ✓
Initializing AI ledger...          ✓
Initializing evolution workspace... ✓
System initialized.
Starting Main Loop...
Starting Discord bot...
Discord bot logged in as Agent Jung#5339
Synced 7 slash commands            ✓ (status, wake, stop, task, evolve, approve, reject)
```

### 2.2 优雅停止

**方法 1**: 在运行窗口按 `Ctrl+C` 一次，等待退出

**方法 2**: Discord 命令
```
/stop
```

**验证停止**:
```
/status
→ System: stopped
→ Supervisor: stopped
```

### 2.3 强制重启

```powershell
# 停止所有 Python 进程
Get-Process python* | Stop-Process -Force

# 重新启动
python main.py
```

---

## 3. Discord 命令操作手册

### 3.1 基础生命周期

#### `/status` - 查看系统状态
```
AegisOS Status
System: running/stopped
Runtime: v1.0
Target: none
Supervisor: running/stopped
Last HB: alive
```

#### `/wake` - 启动 Supervisor
- 设置 `system_state.status = running`
- 启动心跳线程
- 允许任务执行

#### `/stop` - 停止 Supervisor
- 设置 `system_state.status = stopped`
- 停止心跳
- 任务执行暂停（pending 任务保留）

### 3.2 任务管理

#### `/task <text>` - 创建任务
```
/task summarize the quarterly report
→ Task #42 recorded.
```

**任务类型自动识别**:
- 普通文本 → 走 Phase 4 mock 执行
- 包含 `ai:` 前缀 → 走 Phase 5 AI 执行（预算控制）

### 3.3 进化系统（Phase 6）

#### `/evolve <goal>` - 请求 AI 改进系统
```
/evolve improve error handling in task runner
→ Evolution request created.
→ Task: #43
→ Proposal: evo_20260217_143052
→ Status: proposed (awaiting validation)
```

**注意事项**:
- AI 只生成 patch 到 `evolution/proposals/`
- 永不直接修改 runtime
- 受 Phase 5 预算控制

#### `/approve <proposal_id>` - 批准进化提案
```
/approve evo_20260217_143052
→ Proposal evo_20260217_143052 approved.
→ Use /switch to deploy when ready.
```

**重要**: `/approve` 只标记状态，**不自动部署**！

#### `/reject <proposal_id>` - 拒绝提案
```
/reject evo_20260217_143052
→ Proposal evo_20260217_143052 rejected.
```

---

## 4. 预算与成本监控

### 4.1 检查当前预算状态

```sql
-- 查看今日 AI 使用情况
SELECT 
    COUNT(*) AS calls,
    SUM(total_tokens) AS tokens,
    SUM(estimated_cost) AS cost,
    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected
FROM ai_ledger 
WHERE created_at > unixepoch() - 86400;
```

### 4.2 预算限制配置

**硬编码在代码中**:
```python
# aegisos/ai/ledger.py
DAILY_TOKEN_LIMIT = 1000000  # 每日 100 万 tokens
TASK_TOKEN_LIMIT = 100000     # 单次任务 10 万 tokens

MODEL_PRICING = {
    "kimi": (0.50, 2.00)  # (input$/1M, output$/1M)
}
```

**修改预算**: 需重启系统

### 4.3 预算耗尽处理

**现象**: 
```
/evolve improve logging
→ Task created but AI call rejected
→ Ledger shows: status='rejected', reason='Daily budget exceeded'
```

**处理**:
1. 等待次日重置（自动）
2. 或临时提高限制（需改代码重启）
3. 紧急情况下可删除部分 ledger 记录（不推荐，破坏审计）

---

## 5. 数据库维护

### 5.1 检查数据库健康

```python
python -c "
import sqlite3
conn = sqlite3.connect('aegisos.db')
cursor = conn.cursor()

# 检查表结构
tables = ['tasks', 'system_state', 'heartbeats', 'ai_ledger', 'evolution_jobs']
for t in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {t}')
    count = cursor.fetchone()[0]
    print(f'{t}: {count} rows')

conn.close()
"
```

### 5.2 备份数据库

```powershell
# 系统运行时备份（SQLite 支持热备份）
Copy-Item aegisos.db aegisos_backup_$(Get-Date -Format "yyyyMMdd").db

# 或使用命令行
sqlite3 aegisos.db ".backup 'backup.db'"
```

### 5.3 清理旧数据

```sql
-- 保留最近 30 天的详细记录，归档旧数据
DELETE FROM heartbeats WHERE timestamp < unixepoch() - 2592000;

-- 或者导出后删除
.output heartbeats_archive.csv
SELECT * FROM heartbeats WHERE timestamp < unixepoch() - 2592000;
DELETE FROM heartbeats WHERE timestamp < unixepoch() - 2592000;
```

---

## 6. 进化系统运维

### 6.1 查看待处理提案

```sql
-- 查看所有提案状态
SELECT 
    id,
    proposal_path,
    status,
    datetime(created_at, 'unixepoch') as created,
    datetime(validated_at, 'unixepoch') as validated,
    datetime(approved_at, 'unixepoch') as approved
FROM evolution_jobs
ORDER BY created_at DESC;
```

### 6.2 手动检查提案内容

```powershell
# 查看生成的 patch
Get-Content evolution/proposals/evo_20260217_143052/patch.diff

# 查看 manifest
Get-Content evolution/proposals/evo_20260217_143052/manifest.json | ConvertFrom-Json
```

### 6.3 清理 staging 目录

```powershell
# staging 是临时验证区，可随时清理
Remove-Item -Recurse evolution/staging/*
```

### 6.4 危险操作：删除提案

```powershell
# 仅在确认提案有害时执行
Remove-Item -Recurse evolution/proposals/evo_xxx

# 同时更新数据库
sqlite3 aegisos.db "UPDATE evolution_jobs SET status='rejected' WHERE id=x;"
```

---

## 7. 故障排查

### 7.1 系统无响应

**检查清单**:
1. Supervisor 是否运行？`/status`
2. 心跳是否更新？检查 `heartbeats` 表
3. Main Loop 是否卡住？检查控制台输出

**重启**:
```powershell
Get-Process python* | Stop-Process -Force
python main.py
```

### 7.2 AI 调用不执行

**检查**:
```sql
-- 检查 budget 限制
SELECT * FROM ai_ledger ORDER BY id DESC LIMIT 5;

-- 检查是否有 rejected 记录
SELECT * FROM ai_ledger WHERE status='rejected';
```

**常见原因**:
- 预算耗尽
- Task 类型不是 AI 类型（需要 `ai:` 前缀）
- system_state.status = stopped

### 7.3 进化系统不工作

**检查**:
1. 提案是否生成？`evolution/proposals/` 目录
2. Validator 是否运行？检查控制台 `[Validator]` 日志
3. 数据库是否有 evolution_jobs 记录？

**手动触发验证**:
```python
python -c "
from aegisos.evolution.validator import validate_proposal
validate_proposal(1)  # 替换为实际 job_id
"
```

### 7.4 数据库锁定

**现象**: "database is locked"

**解决**:
```powershell
# 找到并终止占用进程
Get-Process python* | Stop-Process -Force

# 或使用命令行查询（不锁定 DB）
sqlite3 aegisos.db ".tables"
```

---

## 8. 安全操作规范

### 8.1 AI 治理红线

**绝对禁止**:
- 修改 `ai/ledger.py` 让 AI 调用绕过记录
- 在 `validator.py` 中添加 AI 调用
- 直接修改 `runtime/` 目录（应通过 evolution）
- 删除或篡改 `ai_ledger` 记录

**审批流程**:
```
/evolve → AI 生成提案 → /approve → 人工审核 → /switch 部署
```

### 8.2 预算异常处理

**如果发现成本异常增长**:

1. 立即停止 Supervisor: `/stop`
2. 查询 ledger:
```sql
SELECT task_id, model, prompt_tokens, completion_tokens, created_at 
FROM ai_ledger 
ORDER BY id DESC 
LIMIT 20;
```
3. 找到异常 task
4. 检查 task payload:
```sql
SELECT payload FROM tasks WHERE id = <task_id>;
```
5. 修复后重启

### 8.3 审计要求

**每日检查**:
```sql
-- AI 财务日报
SELECT 
    DATE(created_at, 'unixepoch') as day,
    COUNT(*) as calls,
    SUM(total_tokens) as tokens,
    SUM(estimated_cost) as cost,
    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as blocked
FROM ai_ledger
GROUP BY day
ORDER BY day DESC;
```

---

## 9. 扩展与升级

### 9.1 添加新模型

修改 `aegisos/ai/ledger.py`:
```python
MODEL_PRICING = {
    "kimi": (0.50, 2.00),
    "gpt-4": (30.00, 60.00),  # 新增
}
```

### 9.2 调整预算限制

修改 `aegisos/ai/ledger.py` 后重启。

### 9.3 Phase 7 准备

当前系统为 Phase 7（AI 能力扩展）预留了接口:
- `task_runner.py` 支持新任务类型
- `ledger.py` 支持多模型
- `evolution/` 支持系统自我改进

---

## 10. 紧急联系与回滚

### 10.1 紧急停止所有 AI 活动

```powershell
# 1. 停止系统
Get-Process python* | Stop-Process -Force

# 2. 修改系统状态（强制 stopped）
sqlite3 aegisos.db "UPDATE system_state SET value='stopped' WHERE key='status';"

# 3. 重启（保持 stopped 状态）
python main.py
```

### 10.2 回滚到上一版本

**数据库回滚**:
```powershell
# 如果有备份
Copy-Item aegisos_backup_20260217.db aegisos.db -Force
```

**代码回滚**:
```bash
git checkout <previous-commit>
```

### 10.3 灾难恢复清单

- [ ] 停止所有 Python 进程
- [ ] 备份当前数据库（即使损坏）
- [ ] 恢复最近的干净数据库备份
- [ ] 检查 `system_state` 表
- [ ] 重启系统
- [ ] 执行 `/status` 验证
- [ ] 执行简单 `/task` 测试

---

## 附录 A: 常用 SQL 查询

```sql
-- 系统健康检查
SELECT key, value, datetime(updated_at, 'unixepoch') 
FROM system_state;

-- 待处理任务
SELECT id, type, status, payload 
FROM tasks 
WHERE status='pending' 
ORDER BY id;

-- 最近的 AI 调用
SELECT id, task_id, model, total_tokens, estimated_cost, status,
       datetime(created_at, 'unixepoch') 
FROM ai_ledger 
ORDER BY id DESC 
LIMIT 10;

-- 进化提案状态
SELECT id, proposal_path, status,
       datetime(created_at, 'unixepoch') as created
FROM evolution_jobs
ORDER BY id DESC;

-- 心跳健康（最近 5 条）
SELECT component, message, runtime_version,
       datetime(timestamp, 'unixepoch') 
FROM heartbeats 
ORDER BY timestamp DESC 
LIMIT 5;
```

---

## 附录 B: 术语表

| 术语 | 定义 |
|------|------|
| **Ledger** | AI 成本审计账本 |
| **Gate** | Main Loop 的执行许可检查点 |
| **Evolution** | 系统自我改进机制（Phase 6） |
| **Proposal** | AI 生成的代码改进方案 |
| **Staging** | 隔离的验证环境 |
| **Runtime** | 当前运行的系统代码 |
| **Tick** | Main Loop 的 10 秒执行周期 |

---

**文档结束**

如有疑问或发现系统异常，请记录详细日志并参考本手册排查。
