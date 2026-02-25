# AegisOS System Validation Checklist

## 自动测试结果

```bash
python test_system_validation.py
```

**结果**: 19/19 通过 ✅

| 类别 | 测试项 | 状态 |
|------|--------|------|
| **P0-1** | Instance Lock (防双开) | ✅ |
| **P0-2** | Database WAL Mode | ✅ |
| **P0-3** | Crash Recovery | ✅ |
| **P4** | Worker Pool (单例/启动/停止) | ✅ |
| **P5** | Budget Limits (四层限制) | ✅ |
| **P5** | Budget Check (拒绝/允许) | ✅ |
| **P5** | Ledger Records | ✅ |
| **Security** | Ledger Enforcement | ✅ |
| **Security** | Evolution Isolation | ✅ |
| **Security** | Memory Read-only | ✅ |
| **P6** | Evolution Jobs Table | ✅ |
| **P7** | Engineering Memory Table | ✅ |
| **Integration** | Task Lifecycle | ✅ |
| **Integration** | Worker Pool Submit | ✅ |

---

## 手动验证步骤

### 1. Worker Pool 模式验证

```powershell
# 1. 启动系统（Worker Pool 模式）
$env:MOONSHOT_API_KEY="sk-your-key"
$env:WORKER_POOL_SIZE="3"
python main.py
```

**预期输出**:
```
[P1-3] Initializing Worker Pool...
[OK] Worker Pool initialized (3 workers)
[OK] Starting Main Loop (Worker Pool mode)...
```

### 2. 并发任务测试

在 Discord 中快速发送多个 AI 任务：
```
/task ai: 任务1
/task ai: 任务2
/task ai: 任务3
/task ai: 任务4
```

**验证点**:
- [ ] 所有任务立即返回 "queued" 响应（非阻塞）
- [ ] 控制台显示 "Active tasks: X"
- [ ] Main Loop 继续 10s tick（不被阻塞）
- [ ] 所有任务最终完成（`/result` 查看）

### 3. 超时处理测试

创建一个长时间运行的任务（模拟）:

```python
# 临时修改 worker.py 中的 timeout
# DEFAULT_TIMEOUT = 5  # 5秒超时测试
```

**验证点**:
- [ ] 超时后任务标记为 failed
- [ ] 任务状态显示 "TIMEOUT"
- [ ] Worker Pool 继续处理其他任务

### 4. Budget 守卫验证

```powershell
# 设置极低的预算测试
$env:TASK_TOKEN_LIMIT="100"
```

在 Discord 中:
```
/task ai: 写一段很长的文章...
```

**验证点**:
- [ ] Budget 预检查拒绝任务
- [ ] Ledger 记录 rejection
- [ ] 返回 "BUDGET_REJECTED" 错误

### 5. 优雅关闭验证

启动系统后，按 `Ctrl+C`:

**验证点**:
- [ ] Worker Pool 停止消息
- [ ] 未完成任务被标记为 cancelled
- [ ] 数据库状态为 "clean" shutdown
- [ ] Lock 文件被释放

### 6. 安全约束验证

**Ledger 不可绕过**:
```python
# 尝试直接调用 kimi_client（应失败）
from aegisos.ai.kimi_client import get_client
client = get_client()
# 无 API key 时应抛出 RuntimeError
```

**Evolution 隔离**:
- [ ] 检查 `aegisos/evolution/proposals/` 目录存在
- [ ] 确认 AI 无法直接修改 runtime 目录

**Memory 只读**:
- [ ] `retrieve_similar_cases()` 只能读取
- [ ] 无 write 函数暴露给 AI

### 7. 故障恢复验证

```powershell
# 1. 启动系统
python main.py

# 2. 强制终止 (模拟崩溃)
Ctrl+Break 或任务管理器结束

# 3. 重新启动
python main.py
```

**验证点**:
- [ ] 检测到 unclean shutdown
- [ ] 之前 running 的任务被重置为 pending
- [ ] 系统正常启动，无数据损坏

---

## 性能基准

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| Main Loop Tick | 10s ± 1s | 观察日志时间戳 |
| Worker 并发 | 3 个任务 | 提交 5 个任务，观察 active count |
| AI 调用超时 | 300s | 设置 mock 延迟 > 300s |
| 任务提交延迟 | < 100ms | 测量 submit() 返回时间 |
| 内存使用 | < 100MB | 任务管理器观察 |

---

## 回滚准备

如需回滚到同步模式：

```powershell
# 从备份恢复
Expand-Archive backups/aegisos_worker_v1_*.zip -DestinationPath . -Force
```

---

## 生产部署前检查

- [ ] 所有自动测试通过
- [ ] 手动验证步骤完成
- [ ] 性能基准达标
- [ ] 备份已创建
- [ ] 回滚方案确认
- [ ] 监控告警配置（Discord/日志）

**验证完成日期**: _______________
**验证人员**: _______________
