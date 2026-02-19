# AegisOS Worker Pool 模式 (Phase 5C)

## 架构变更

```
Before (同步阻塞):
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Main Loop  │────▶│  Task Exec  │────▶│   Blocked   │  (60s+)
│   (10s)     │     │  (AI Call)  │     │   (Wait)    │
└─────────────┘     └─────────────┘     └─────────────┘

After (Worker Pool):
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Main Loop  │────▶│   Submit    │────▶│  Continue   │  (Non-blocking)
│   (10s)     │     │   (Gate)    │     │   (Next)    │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Worker Pool │     (Async Execution)
                    │  (3 workers)│     (5min timeout)
                    └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Ledger    │     (Budget tracking)
                    │    + DB     │     (State update)
                    └─────────────┘
```

## 设计原则遵守

| 原则 | 实现 |
|------|------|
| **Gate 控制** | ✅ Main Loop 检查 status、budget 后才 submit |
| **Budget 守卫** | ✅ Pre-check 在 submit，Ledger 在 execution |
| **单实例** | ✅ Worker Pool 是单例，线程安全 |
| **Supervisor** | ✅ 心跳不受影响，Main Loop 每 10s 运行 |
| **Ledger** | ✅ execute_with_budget_guard 仍在 Worker 中调用 |

## 配置

### 环境变量

| 变量 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `MOONSHOT_API_KEY` | 启用 AI 时 | - | Kimi API Key |
| `WORKER_POOL_SIZE` | 否 | `3` | Worker 线程数 |
| `MOONSHOT_MODEL` | 否 | `kimi-k2.5` | 模型名称 |

### 启动

```powershell
$env:MOONSHOT_API_KEY="sk-your-key"
$env:WORKER_POOL_SIZE="3"
python main.py
```

## 启动日志

```
======================================================================
AEGISOS PRODUCTION HARDENED STARTUP (Worker Pool Mode)
======================================================================
[P0-1] Instance lock acquired (mode: clean)
[P0-2] Initializing database with WAL mode...
[P0-3] Last shutdown was clean
[P1-1] Initializing AI ledger and budget guard...
[P1-2] Checking Kimi API configuration...
[P1-2] Kimi client configured (API key: sk-xxxx...)
[OK] Kimi API enabled - AI tasks will use real model
[P1-3] Initializing Worker Pool...
[OK] Worker Pool initialized (3 workers)
[P2-1] Initializing evolution workspace...
[P3-1] Building engineering memory index...
[OK] System initialized.
======================================================================
[OK] Starting Main Loop (Worker Pool mode)...
[OK] Starting Discord bot...
```

## 任务执行流程

```
Discord /task ai: 你好
    ↓
Task #5 created (status=pending)
    ↓
Main Loop (next tick)
    ├── Check status == "running" ✅
    ├── Budget pre-check ✅
    └── Submit to Worker Pool
        └── Task #5 (status=running in Worker)
    ↓
Main Loop continues (10s tick)
    └── Not blocked!
    ↓
Worker executes AI call (up to 5min)
    ├── Kimi API call
    ├── Ledger write
    └── DB update (completed)
    ↓
/result 5 查看结果
```

## 超时处理

| 场景 | 行为 |
|------|------|
| AI 调用 5 分钟未完成 | Worker 标记 timeout，任务失败 |
| Main Loop 卡住 60 分钟 | Anti-deadlock 重置不在 Worker 中的任务 |
| 优雅关闭 | Worker Pool 等待 30s 完成或取消任务 |

## 监控

### Discord 命令

```
/status          - 查看系统状态（显示 active tasks）
/result <id>     - 查看任务结果
```

### 控制台日志

```
[Main Loop] Task 5 submitted to worker pool
[Main Loop] Active tasks: 2
[WorkerPool] Task 5 completed (245 tokens)
```

## 回滚

如需回滚到同步模式，恢复备份：

```powershell
# 从备份恢复
Expand-Archive backups/aegisos_backup_20260217_215651.zip -DestinationPath . -Force
```
