# AegisOS GitHub 发布指南

## 准备状态

项目已清理完毕，可以安全发布到 GitHub。

### 已完成的清理工作

✅ **删除敏感信息**
- Discord Token 已从 config.yaml 移除（改为从环境变量读取）
- Moonshot API Key 已从 config.yaml 移除（改为从环境变量读取）
- Discord User IDs 和 Channel IDs 已替换为占位符

✅ **删除无关文件**
- 46 个 .pyc 文件已删除
- 12 个 __pycache__ 目录已删除
- 运行时数据库文件已删除 (aegisos.db, aegisos.lock)
- 日志文件已清理
- 备份文件已清理

✅ **创建 .gitignore**
- Python 缓存文件
- 数据库文件
- 日志文件
- 环境变量文件
- IDE 配置文件

---

## 发布步骤

### 第一步：安装 Git

如果尚未安装 Git，请从 https://git-scm.com/download/win 下载并安装。

### 第二步：初始化 Git 仓库

打开 PowerShell，执行：

```powershell
cd C:\AegisOS
git init
```

### 第三步：配置 Git（如果尚未配置）

```powershell
git config user.email "your-email@example.com"
git config user.name "Your Name"
```

### 第四步：添加文件到仓库

```powershell
git add .
```

### 第五步：创建初始提交

```powershell
git commit -m "Initial commit: AegisOS v1.0 MVP

Features:
- Phase 1-6: Complete runtime with governed optimization
- Budget control: $5/day default with token tracking
- Rate limiting: 5 tasks/min with sliding window
- Governance: AI proposes, system validates, human approves
- Shadow execution: Zero-impact strategy validation
- Version control: Strategy switching with rollback
- Discord interface: Slash commands with usage tracking

Safety:
- No hardcoded secrets (env vars only)
- No auto-execution (human approval required)
- No auto-switching (manual trigger only)"
```

### 第六步：创建 GitHub 仓库

1. 访问 https://github.com/new
2. 输入仓库名称：`AegisOS`
3. 选择公开或私有
4. **不要**初始化 README（我们已经有 README 文件）
5. 点击 "Create repository"

### 第七步：推送到 GitHub

在 GitHub 创建仓库后，执行：

```powershell
git remote add origin https://github.com/YOUR_USERNAME/AegisOS.git
git branch -M main
git push -u origin main
```

将 `YOUR_USERNAME` 替换为你的 GitHub 用户名。

---

## 发布前检查清单

### 敏感信息检查

运行以下命令确认没有敏感信息：

```powershell
# 搜索可能的敏感信息
grep -r "sk-[a-zA-Z0-9]" . --include="*.py" --include="*.yaml" --include="*.yml" --include="*.json" --include="*.md"
grep -r "token.*=" . --include="*.py" --include="*.yaml" | grep -v "from_env" | grep -v "getenv"
```

### 文件检查

确认以下文件已被 .gitignore 排除：

```powershell
# 检查是否有数据库文件
git check-ignore -v aegisos.db
git check-ignore -v logs/test.log

# 检查是否有 pycache
git check-ignore -v aegisos/__pycache__
```

---

## 环境变量配置

用户克隆仓库后，需要设置以下环境变量：

```powershell
# Discord Bot Token
$env:DISCORD_TOKEN="your-discord-bot-token"

# Moonshot API Key (可选，用于真实 AI 调用)
$env:MOONSHOT_API_KEY="sk-your-moonshot-api-key"
```

或者创建 `.env` 文件（已添加到 .gitignore）：

```
DISCORD_TOKEN=your-discord-bot-token
MOONSHOT_API_KEY=sk-your-moonshot-api-key
```

---

## 后续管理

### 日常开发流程

```powershell
# 1. 创建新分支
git checkout -b feature/new-feature

# 2. 修改代码...

# 3. 提交更改
git add .
git commit -m "Add new feature"

# 4. 推送到远程
git push origin feature/new-feature

# 5. 在 GitHub 创建 Pull Request 进行代码审查
```

### 更新依赖

```powershell
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update dependencies"
git push
```

---

## 项目结构（发布版）

```
AegisOS/
├── .gitignore              # Git 忽略规则
├── config.yaml             # 配置文件（占位符，需用户配置）
├── config.yaml.example     # 配置示例
├── requirements.txt        # Python 依赖
├── main.py                 # 入口点
├── AGENTS.md               # 项目文档
├── GITHUB_PUBLISH_GUIDE.md # 本文件
├── aegisos/                # 核心代码
│   ├── ai/                 # AI 客户端
│   ├── audit/              # 审计日志
│   ├── core/               # 核心组件
│   ├── db/                 # 数据库层
│   ├── executor/           # 执行器
│   ├── infra/              # 基础设施
│   ├── intelligence/       # 智能优化
│   └── interfaces/         # 外部接口
├── config/                 # 配置目录
└── docs/                   # 文档
```

---

## 许可证建议

考虑添加开源许可证，例如 MIT：

```powershell
# 创建 LICENSE 文件
@"
MIT License

Copyright (c) 2026 [Your Name]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"@ | Out-File -FilePath "C:\AegisOS\LICENSE" -Encoding utf8
```

---

## 安全提示

⚠️ **永远不要提交到 GitHub 的内容：**

1. `.env` 文件（包含真实 token）
2. `aegisos.db` 数据库文件（包含运行时数据）
3. `logs/` 目录下的日志文件
4. 任何包含 API Key、Password、Token 的临时文件

✅ **当前仓库状态：** 已清理，可以安全发布

---

## 需要帮助？

如果遇到问题：

1. 检查 Git 是否安装：`git --version`
2. 检查远程仓库：`git remote -v`
3. 检查当前分支：`git branch`
4. 查看 GitHub 文档：https://docs.github.com/
