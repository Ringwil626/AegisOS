# AegisOS Discord 频道设置指南

## 推荐频道架构

基于手机端友好和权限分离原则，建议设置以下频道：

```
📁 AegisOS Server
├── 💬 #ai-tasks          (用户交互 - 读写)
├── 📊 #system-status     (系统状态 - 只读)
├── 📋 #task-status       (任务状态 - 只读)
├── 🚨 #alerts            (告警通知 - 只读)
└── 🔧 #dev-logs          (开发调试 - 可选)
```

## 频道详细说明

### 1. #ai-tasks (用户交互频道)

**用途**: 接收用户指令，AI 交互

**权限**:
- 管理员: 读写 + 管理消息
- 普通用户: 读写（发送指令）
- Bot: 读写（回复消息）

**支持的指令**:
```
/status  - 查看系统状态
/wake    - 启动 Supervisor
/stop    - 停止 Supervisor
/task    - 创建新任务
/approve - 批准任务执行
/execute - 执行已批准任务
/projects - 列出项目
```

**消息格式**:
- 使用 Embed 显示任务结果
- 长输出使用线程(Thread)或代码块折叠

### 2. #system-status (系统状态频道)

**用途**: 展示系统运行状态

**权限**:
- 所有人: 只读
- Bot: 读写（推送状态）

**推送内容**:
```yaml
推送频率: 状态变化时（避免定时刷屏）
内容:
  - Supervisor 运行状态
  - Runtime 版本号
  - 数据库心跳
  - 任务队列统计
  - AI Token 使用量
```

**Embed 格式示例**:
```
🟢 AegisOS System Status
━━━━━━━━━━━━━━━━━━━━━━
Supervisor:  Running  ✅
Runtime:      v1.0-worker
Database:     Heartbeat OK
Tasks:        5 Pending | 2 Running
Token Usage:  9,520 / 150,000 (6%)
Last Update:  2 minutes ago
```

### 3. #task-status (任务执行状态)

**用途**: 任务生命周期追踪

**权限**:
- 所有人: 只读
- Bot: 读写（推送状态）

**推送时机**:
- 任务创建
- 任务开始执行
- 任务完成/失败

**消息格式**:
```
✅ Task #42 COMPLETED  [pdf_extractor]
━━━━━━━━━━━━━━━━━━━━━━
Command: ai analyze project structure
Status:  completed
Result:  {"actions": [...], "explanation": "..."}
Time:    2m 34s

📋 Use `/result 42` for full details
```

### 4. #alerts (告警频道)

**用途**: Critical errors, 系统异常

**权限**:
- 所有人: 只读
- Bot: 读写（推送告警）

**触发条件**:
- 系统崩溃或重启
- 任务执行超时
- AI 调用失败（多次重试后）
- 数据库连接异常
- 治理合规检查失败

**Embed 格式** (按级别着色):
```yaml
🚨 Critical (深红色):
  - 系统崩溃
  - 数据库损坏

❌ Error (红色):
  - 任务连续失败
  - API 认证失败

⚠️ Warning (橙色):
  - 任务超时
  - 配额即将耗尽

ℹ️ Info (蓝色):
  - 系统重启
  - 版本切换完成
```

### 5. #dev-logs (开发调试 - 可选)

**用途**: 开发调试信息

**权限**:
- 开发者: 读写
- Bot: 读写

**内容**:
- PR 合规检查报告
- AI 自检结果
- 详细调试日志

## config.yaml 配置

```yaml
discord:
  token: "YOUR_BOT_TOKEN"
  
  # 命令频道（#ai-tasks）
  command_channel:
    - "CHANNEL_ID_FOR_AI_TASKS"
  
  # 状态推送频道
  channels:
    system_status: "CHANNEL_ID_FOR_SYSTEM_STATUS"  # #system-status
    task_status: "CHANNEL_ID_FOR_TASK_STATUS"      # #task-status
    alerts: "CHANNEL_ID_FOR_ALERTS"                # #alerts
    dev_logs: "CHANNEL_ID_FOR_DEV_LOGS"            # #dev-logs (可选)
```

## 权限设置最佳实践

### 角色设计

```
👑 Admin (管理员)
├── 所有权限
├── 可以执行 /wake, /stop
└── 可以批准任务执行

👤 User (普通用户)
├── #ai-tasks: 读写
├── #system-status: 只读
├── #task-status: 只读
├── #alerts: 只读
└── 可以创建任务，但不能批准

🤖 Bot
├── 所有频道: 读写
└── 管理消息权限（用于清理旧消息）

🔇 @everyone
├── 所有频道: 无权限
└── 需要分配角色后才能访问
```

### 频道权限设置

**#ai-tasks**:
```
@everyone: ❌ View Channel
Admin: ✅ Send Messages, Manage Messages
User: ✅ Send Messages, Add Reactions
Bot: ✅ All
```

**#system-status, #task-status, #alerts**:
```
@everyone: ❌ View Channel
Admin: ✅ View Channel
User: ✅ View Channel, Add Reactions
Bot: ✅ Send Messages, Manage Messages
```

## 手机端优化

### 消息设计原则

1. **简洁标题**: 一眼看到关键信息
2. **Emoji 标识**: 快速识别状态
3. **避免长文本**: 使用折叠或线程
4. **时间戳**: 相对时间（2分钟前）比绝对时间友好

### 推送频率控制

```yaml
#system-status:
  正常: 状态变化时推送
  异常: 立即推送

#task-status:
  每个任务: 开始 + 完成/失败时推送
  避免: 每几秒推送一次

#alerts:
  所有: 立即推送（高优先级）
```

## 实施步骤

### 1. 创建 Discord 服务器

1. 打开 Discord
2. 点击 "+" 创建服务器
3. 选择 "Create My Own"
4. 命名: "AegisOS Control"

### 2. 创建频道

按上述架构创建文本频道

### 3. 创建 Bot

1. 访问 https://discord.com/developers/applications
2. New Application → 命名
3. Bot → Add Bot
4. 复制 Token（用于 config.yaml）
5. OAuth2 → URL Generator:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions:
     - Send Messages
     - Manage Messages
     - Embed Links
     - Read Message History
     - Use Slash Commands

### 4. 邀请 Bot

使用生成的 URL 邀请 Bot 到服务器

### 5. 配置权限

按上述权限表设置频道权限

### 6. 获取频道 ID

1. Discord 设置 → 高级 → 开发者模式: 开启
2. 右键频道 → Copy Channel ID
3. 填入 config.yaml

### 7. 启动 AegisOS

```bash
python main.py
```

验证 Bot 在线，测试各频道功能。

## 故障排查

### Bot 不在线

- 检查 Token 是否正确
- 检查 Bot 是否被邀请进服务器

### 消息不推送

- 检查频道 ID 是否正确
- 检查 Bot 是否有发送权限

### 指令无响应

- 检查 command_channel 配置
- 检查用户是否有权限
- 查看 Bot 日志

## 参考

- Discord Developer Portal: https://discord.com/developers/applications
- discord.py 文档: https://discordpy.readthedocs.io/
- AegisOS GOVERNANCE.md
