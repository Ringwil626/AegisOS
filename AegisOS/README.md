# AegisOS

**A Deterministic Execution OS with an Attached Reasoning Engine**

[![Status](https://img.shields.io/badge/status-production%20hardened-green)]()

AegisOS 是一个用于管理 AI 辅助任务的确定性执行运行时。它不是 AI Agent，也不是自进化系统——它是一个**操作系统**，其中 AI 是可调用的工具，而非控制器。

> **核心原则**: SQLite 是唯一真相源，AI 是工具，人类掌控进化。

---

## 🚀 开箱即用

```bash
# 1. 克隆项目
git clone https://github.com/Ringwil626/AegisOS.git
cd AegisOS

# 2. 启动 Jung 界面（推荐）
./start.sh --jung

# 或使用默认启动（自动检测）
./start.sh
```

**无需配置即可运行** - 系统会自动使用 mock AI 模式。如需启用真实 AI，设置环境变量即可。

---

## 🎭 Jung 界面（新）

AegisOS 现在有一个具有 **Jung 人格特质**的交互界面：

- **分析风格**: 拆解问题、指出模式、结构化思考
- **俏皮风格**: 轻松幽默、偶尔自嘲、带梗
- **沉思风格**: 缓慢深入、存在主义、诗意
- **直接风格**: 简洁无废话、有判断

### 使用 Jung 界面

```bash
./start.sh --jung
```

示例对话：
```
jung> 你好
嗯，我在。

jung> 系统状态如何？
系统当前 running，有 2 个任务在队列中等待。

这种等待不是停滞，而是准备。

jung> 哈哈，这系统挺有意思
有趣是个好的开始。保持好奇心，这是人类的优势。

jung> 为什么我们要约束AI？
看着 AegisOS 在 running 状态运行，我会想到一个问题：

当我们设计一个系统来约束 AI 时，
我们其实是在回答一个更古老的问题——
自由与安全的边界在哪里？

当前有 2 个任务在等待。
每一个都是某个意图的具象化，
在这个确定性的沙盒里寻找出口。
```

---

## 📋 运行模式

| 模式 | 命令 | 说明 |
|------|------|------|
| **Jung 界面** | `./start.sh --jung` | **推荐** - 有 Jung 人格的交互界面 |
| CLI 交互 | `./start.sh --cli` | 纯命令行模式 |
| 演示模式 | `./start.sh --demo` | 创建示例任务并运行 |
| 后台 | `./start.sh --no-discord` | 仅主循环，无界面 |
| 完整模式 | `./start.sh` | 需要 DISCORD_TOKEN |

---

## 🔧 配置

### 环境变量（推荐）

```bash
# AI API (月之暗面 Kimi)
export MOONSHOT_API_KEY="sk-your-key-here"

# Discord Bot (可选)
export DISCORD_TOKEN="your-discord-bot-token"
```

### 配置文件

编辑 `config.yaml` 调整：
- 预算限制（日/小时/月 token 配额）
- 监控间隔
- 日志级别

---

## 🏗️ 架构

```
Layer 1 — Core Runtime (supervisor, executor, db)  ← AI 不可触碰
    ↓
Layer 2 — Execution (inference_executor - SINGLE AI GATE)  ← AI 唯一入口
    ↓
Layer 3 — Interface (Discord/CLI)
    ↓
Layer 4 — Governance (human-approved changes)
    ↓
Layer 5 — Project Space (user code)  ← AI 只能在这里工作
```

### 核心安全机制

1. **DB Write Firewall** - AI 不能直接写入核心表
2. **预算硬限制** - 调用 AI 前强制检查预算
3. **实例锁** - 防止多实例冲突
4. **WAL 模式** - SQLite 数据完整性保障

---

## 💻 命令

在 Jung 界面或 CLI 模式下可用：

```
jung> status          # 查看系统状态
jung> wake            # 启动系统
jung> stop            # 停止系统
jung> task <text>     # 创建任务
jung> evolve <goal>   # 创建进化提案
jung> budget          # 查看预算
jung> exit            # 退出
```

### 任务类型

```
# 普通任务
jung> task echo hello world

# AI 任务（使用 mock AI，无需 API key）
jung> task ai: 解释什么是确定性执行

# Kimi 任务（需要 MOONSHOT_API_KEY）
jung> task kimi: 分析这段代码的问题
```

### 随意聊聊

Jung 界面支持自然对话：
```
jung> 你好
jung> 今天怎么样
jung> 你觉得 AegisOS 的设计如何
jung> 什么是自由与安全的边界
```

---

## 🧬 进化工作流 (Phase 6)

AegisOS 支持**受控的自我进化**：

1. 用户提出进化目标: `/evolve "添加任务统计功能"`
2. AI 生成提案（带历史上下文和风险评估）
3. 自动验证提案格式
4. 人类审批: `/approve <proposal_id>`
5. 部署更新

AI 可以提议，但执行必须人工审批。

---

## 💰 预算控制

三层预算保护：

| 层级 | 限制 | 说明 |
|------|------|------|
| 单次任务 | 25K tokens | 防止单次爆炸 |
| 每小时 | 40K tokens | 防突发流量 |
| 每日 | 150K tokens | 约 ¥5 预算 |

预算报告：
```
💰 AI Budget Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 Hourly:  0 / 40,000 (0.0%) ~¥0.0
🟢 Daily:   0 / 150,000 (0.0%) ~¥0.0
🟢 Monthly: 0 / 4,500,000 (0.0%) ~¥0.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 🧪 测试

```bash
# 运行完整测试套件
python test_all.py
```

---

## 📁 项目结构

```
AegisOS/
├── main.py                 # 主入口
├── start.sh               # 启动脚本
├── test_all.py            # 测试套件
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖
├── aegisos/
│   ├── core/              # 核心运行时
│   │   ├── supervisor.py  # 监控器
│   │   ├── instancelock.py # 实例锁
│   │   └── health.py      # 健康检查
│   ├── db/                # 数据库层
│   │   └── sqlite_store.py
│   ├── ai/                # AI 治理
│   │   ├── executor.py    # 预算守卫执行
│   │   ├── ledger.py      # 用量账本
│   │   └── kimi_client.py # Kimi API 客户端
│   ├── executor/          # 任务执行
│   │   └── task_runner.py
│   ├── evolution/         # 进化管理
│   │   └── manager.py
│   ├── memory/            # 向量记忆
│   │   └── vector_index.py
│   └── interfaces/        # 接口层
│       └── discord_bot.py
├── evolution/             # 进化提案存储
│   ├── proposals/
│   └── staging/
└── projects/              # 项目工作区
    └── default/
```

---

## 📖 文档

- [GOVERNANCE.md](GOVERNANCE.md) - 治理规则和开发规范
- [EXECUTOR_CONTRACT.md](EXECUTOR_CONTRACT.md) - 执行器契约
- [INFERENCE_CONTRACT.md](INFERENCE_CONTRACT.md) - 推理契约
- [PROMPT_CONTRACT.md](PROMPT_CONTRACT.md) - Prompt 契约

---

## 🤝 贡献

遵循 [GOVERNANCE.md](GOVERNANCE.md) 中的开发规则：

1. 不写 Agent 框架，写基础设施
2. 不把控制逻辑放进 prompt
3. DB 拥有现实，无隐藏状态
4. Supervisor 保持愚蠢（只发心跳）
5. AI 是工具，不是大脑

---

## 📜 许可证

MIT License

---

**AegisOS**: SQLite is ground truth. AI is callable. Human governs evolution.
