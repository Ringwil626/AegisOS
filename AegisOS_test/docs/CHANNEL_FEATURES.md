# AegisOS Discord 频道功能完整文档

## 配置说明

### config.yaml

```yaml
discord:
  # 命令频道白名单（机器人只在这些频道响应命令）
  command_channel:
    - "1471154822404112576"  # 主要命令频道
  
  # 推送频道配置
  channels:
    task_status: "1471740828073464014"    # 任务完成推送
    system_status: "1471802761434628136"  # 系统状态推送
```

## 功能详解

### 1. 命令频道限制 ✅

**作用**：机器人只在指定的命令频道响应斜杠命令

**配置**：`discord.command_channel` 列表

**行为**：
- 在白名单频道：命令正常执行
- 在其他频道：返回 "❌ Command not allowed in this channel."

**示例**：
```
# 在正确频道
/task ai: 分析代码 ✅

# 在错误频道  
/task ai: 分析代码 ❌ Command not allowed in this channel.
```

**实现文件**：`aegisos/interfaces/discord_bot.py` - `check_command_channel()`

---

### 2. 任务完成推送 ✅

**作用**：任务完成后自动推送到指定频道

**配置**：`discord.channels.task_status`

**触发时机**：
- AI 任务成功完成
- 任务超时失败
- 任务执行出错

**推送内容**：
```
✅ Task #28 COMPLETED `[pdf_extractor]`
📝 ai 分析代码结构
```
Analysis complete...
Use `/result 28` for details.
```

**实现机制**：
- Worker Pool 完成任务 → 写入消息队列 → Bot 消费并发送
- 线程安全：使用 `queue.Queue` 跨线程通信
- 文件：`aegisos/core/message_queue.py`, `aegisos/core/worker.py`

---

### 3. 系统状态推送 ✅

**作用**：定时推送系统运行状态

**配置**：`discord.channels.system_status`

**推送频率**：每 30 秒（当系统 running 时）

**推送内容**：
```
🟢 AegisOS Status `v1.0-worker`
System: **RUNNING**
Active Tasks: 2 | Daily Tokens: 45,230
Last Update: 2 minutes ago
```

**实现机制**：
- Main Loop 定时生成消息 → 写入消息队列 → Bot 消费并发送
- 文件：`main.py`, `aegisos/core/message_queue.py`

---

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Discord Server                          │
├───────────────────────────┬─────────────────────────────────────┤
│  Command Channel          │  Status Channels                    │
│  (1471154822404112576)    │  (1471740828073464014)              │
│                           │  (1471802761434628136)              │
└───────────┬───────────────┴─────────────────────────────────────┘
            │                           ▲
            │  /task, /status...        │  Push notifications
            ▼                           │
┌───────────────────────────┐          │
│    Discord Bot (main)     │          │
│  ├─ Command handlers      │          │
│  ├─ Channel check         │          │
│  └─ Message consumer ◄────┴──────────┘
│         │                     ▲
│         │  asyncio.Queue      │
│         ▼                     │
│  ┌───────────────────┐        │
│  │  Message Queue    │────────┘
│  └───────────────────┘
└───────────┬─────────────────┘
            │  Thread-safe
            ▼
┌──────────────────────────────────────────┐
│          AegisOS Core                    │
│  ┌──────────────┐    ┌──────────────┐   │
│  │ Worker Pool  │───►│ Message Queue│   │
│  │ (Thread)     │    │              │   │
│  └──────────────┘    └──────────────┘   │
│  ┌──────────────┐                       │
│  │ Main Loop    │───────────────────────┤
│  │ (10s tick)   │                       │
│  └──────────────┘                       │
└──────────────────────────────────────────┘
```

---

## 权限设置

### Bot 需要以下权限：

1. **命令频道**：
   - `Send Messages`
   - `Send Messages in Threads`
   - `Use Slash Commands`
   - `Read Message History`

2. **推送频道**：
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`

### 邀请链接示例：
```
https://discord.com/api/oauth2/authorize?
  client_id=YOUR_CLIENT_ID&
  permissions=274877910016&
  scope=bot%20applications.commands
```

---

## 故障排查

### 命令无响应
1. 检查 Bot 是否在命令频道
2. 检查 `config.yaml` 中的 `command_channel` ID 是否正确
3. 检查 Bot 权限

### 推送未生效
1. 检查日志：`[Discord Bot] Message sent to X`
2. 检查频道 ID 是否正确
3. 检查 Bot 是否有该频道的发送权限
4. 检查消息队列：`[MessageQueue] Task #X notification queued`

### 修改配置后
配置修改后需要重启系统：
```bash
python main.py
```

---

## 测试验证

启动系统后检查日志：
```
[Discord Bot] Message queue consumer started
Synced 10 slash commands
```

执行命令测试：
```
/task ai: 测试推送功能 project=pdf_extractor
```

预期结果：
1. 命令在正确频道正常执行
2. 命令在错误频道被拒绝
3. 任务完成后推送频道收到通知
4. 每 30 秒系统状态频道收到更新
