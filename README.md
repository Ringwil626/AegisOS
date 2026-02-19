# AegisOS

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

AegisOS 是一个受控的 AI 代理调度平台，提供预算控制、审计追踪、治理合规和受监管的优化能力。

> **核心理念**: AI 提出 → 系统验证 → 人工批准 → 影子测试 → 切换版本

## ✨ 核心特性

### 🛡️ 安全治理
- **预算控制**: $5/天默认限制，硬停止机制
- **速率限制**: 5 任务/分钟滑动窗口
- **审计追踪**: 完整的 Token 和成本记录
- **影子验证**: 零影响策略测试

### 🤖 智能优化 (Phase 6)
- **行为分析**: 自动检测异常（成功率、Token 消耗、延迟）
- **策略生成**: AI 提出优化建议但不直接执行
- **人工批准**: Discord 命令审批流程
- **版本控制**: 策略切换与回滚能力

### 📊 监控与告警
- **Discord 集成**: 斜杠命令、Embed 消息、线程日志
- **实时状态**: 任务队列、Token 使用、预算状态
- **治理报告**: PR 合规检查、违规扫描

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/AegisOS.git
cd AegisOS
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```powershell
# Windows PowerShell
$env:DISCORD_TOKEN="your-discord-bot-token"
$env:MOONSHOT_API_KEY="sk-your-moonshot-api-key"  # 可选
```

或创建 `.env` 文件：

```
DISCORD_TOKEN=your-discord-bot-token
MOONSHOT_API_KEY=sk-your-moonshot-api-key
```

### 4. 配置 Discord 频道

编辑 `config.yaml`，填入你的 Discord 频道 ID：

```yaml
discord:
  admin_users:
    - "YOUR_DISCORD_USER_ID"
  command_channel:
    - "YOUR_COMMAND_CHANNEL_ID"
  channels:
    system_status: "YOUR_STATUS_CHANNEL_ID"
    task_status: "YOUR_TASK_CHANNEL_ID"
```

### 5. 运行

```bash
python main.py
```

## 📁 项目结构

```
AegisOS/
├── aegisos/
│   ├── ai/              # AI 客户端 (Kimi/Moonshot)
│   ├── audit/           # 审计日志
│   ├── core/            # 核心组件 (Executor, Supervisor)
│   ├── db/              # 数据库层
│   ├── executor/        # 任务执行器
│   ├── infra/           # 基础设施
│   ├── intelligence/    # 智能优化 (Phase 6)
│   └── interfaces/      # Discord Bot
├── config/              # 配置文件
├── docs/                # 文档
├── main.py              # 入口点
└── requirements.txt     # 依赖
```

## 🎮 Discord 命令

| 命令 | 描述 |
|------|------|
| `/status` | 系统健康状态 |
| `/usage` | Token 和成本使用统计 |
| `/proposals` | 查看优化提案 |
| `/strategy` | 策略版本管理 |

## 🛠️ 开发指南

### 运行测试

```bash
# Phase 6 验收测试
python test_phase6_acceptance.py

# 安全检查
python check_security.py

# 治理检查
python check_governance.py
```

### 预算配置

编辑 `config.yaml` 调整预算限制：

```yaml
quota:
  total_weekly_tokens: 2048000
  warning_threshold: 0.8
  critical_threshold: 0.95
```

## 📖 文档

- [AGENTS.md](AGENTS.md) - 项目架构和开发指南
- [GOVERNANCE.md](GOVERNANCE.md) - 治理规则和安全策略
- [EXECUTOR_CONTRACT.md](EXECUTOR_CONTRACT.md) - 执行器契约
- [DISCORD_SETUP.md](DISCORD_SETUP.md) - Discord 配置指南
- [GITHUB_PUBLISH_GUIDE.md](GITHUB_PUBLISH_GUIDE.md) - GitHub 发布指南

## 🔒 安全

### 治理规则

- ❌ AI 绝不直接修改系统
- ❌ 禁止自动执行优化
- ❌ 禁止自动切换模型
- ✅ 人工批准所有变更
- ✅ 影子验证所有策略
- ✅ 支持随时回滚

### 环境变量

所有敏感信息通过环境变量管理：

| 变量 | 描述 | 必需 |
|------|------|------|
| `DISCORD_TOKEN` | Discord Bot Token | 是 |
| `MOONSHOT_API_KEY` | Kimi API Key | 否 |

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Discord UI                          │
│              (Slash Commands, Embeds, Threads)             │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                      Supervisor                             │
│              (Lifecycle Controller, Health)                 │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                       Executor                              │
│         (State Machine, Budget Gate, Timeout)               │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                     AI Client                               │
│              (Stateless, Retry, Ledger)                     │
└─────────────────────────────────────────────────────────────┘
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Moonshot AI](https://moonshot.cn/) - Kimi API
- [Discord.py](https://discordpy.readthedocs.io/) - Discord Bot 框架

---

**注意**: 这是一个研究原型系统，用于探索 AI 代理的安全治理模式。生产环境使用前请进行充分测试。
