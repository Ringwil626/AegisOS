# Discord 频道推送功能

AegisOS 支持自动推送通知到指定的 Discord 频道。

## 配置

在 `config.yaml` 中配置：

```yaml
discord:
  channels:
    task_status: "1471740828073464014"    # 任务完成推送频道
    system_status: "1471802761434628136"  # 系统状态推送频道
```

## 功能说明

### 1. 任务完成推送 (task_status)

**触发时机**: Worker Pool 中的任务完成时

**推送内容**:
- 任务 ID 和状态 (✅ 完成 / ❌ 失败)
- 项目名称
- 任务名称（指令）
- 结果摘要
- 查看详情命令

**示例**:
```
✅ Task #23 COMPLETED `[pdf_extractor]`
📝 ai: 了解这个项目的一切
```
Result summary here...
Use `/result 23` for details.
```

### 2. 系统状态推送 (system_status)

**触发时机**: 每 30 秒（当系统 running 时）

**推送内容**:
- 系统状态（运行中/停止）
- Supervisor 状态
- 活跃任务数
- 今日 AI Token 使用量
- 最后更新时间

**示例**:
```
🟢 AegisOS Status `v1.0-worker`
System: **RUNNING** | Supervisor: **RUNNING**
Active Tasks: 2 | 45,230 tokens used today
Last Update: 2 minutes ago
```

## Bot 权限要求

确保 Bot 在目标频道有以下权限：
- `Send Messages`
- `View Channel`
- `Read Message History`

## 故障排查

### 推送未生效

1. **检查频道 ID**
   ```python
   # 在 Discord 中开启开发者模式，右键频道复制 ID
   ```

2. **检查 Bot 权限**
   - 邀请 Bot 时添加 `Send Messages` 权限
   - 或手动在频道权限设置中允许

3. **检查日志**
   ```
   [Discord Push] Task #X completion pushed to channel Y
   [Discord Push] System status pushed to channel Y
   ```

4. **频道未找到**
   ```
   [Discord Push] Task status channel X not found
   ```
   - 确认 Bot 已加入该服务器
   - 确认 Bot 可以访问该频道

## 禁用推送

将对应配置设为空或删除：

```yaml
discord:
  channels:
    task_status: ""      # 禁用任务推送
    system_status: ""   # 禁用状态推送
```

## 自定义推送

可以在代码中调用推送函数：

```python
from aegisos.interfaces.discord_bot import push_task_completion, push_system_status
import asyncio

# 推送任务完成
await push_task_completion(
    task_id=1,
    task_name="ai: analyze code",
    project="myproject",
    status="completed",
    result_summary="Analysis complete"
)

# 推送系统状态
await push_system_status()
```
