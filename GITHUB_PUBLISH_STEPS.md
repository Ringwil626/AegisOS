# AegisOS 发布到 GitHub 完整流程

## 前置条件

1. 已安装 Git: https://git-scm.com/download/win
2. 已有 GitHub 账号: https://github.com/signup

---

## 第一步：在 GitHub 创建仓库

### 1.1 登录 GitHub
打开 https://github.com/login 登录你的账号

### 1.2 创建新仓库
1. 点击右上角 **+** 号 → **New repository**
2. 填写信息：
   - **Repository name**: `AegisOS` (或你喜欢的名字)
   - **Description**: `A controlled AI agent scheduling platform with governance compliance`
   - **Visibility**: 选择 Public（公开）或 Private（私有）
   - **Initialize this repository with**: ❌ **不要勾选** Add a README
3. 点击 **Create repository**

### 1.3 复制仓库地址
创建后，页面会显示仓库地址，复制 HTTPS 地址：
```
https://github.com/你的用户名/AegisOS.git
```

---

## 第二步：本地初始化 Git

打开 **PowerShell** 或 **CMD**，执行以下命令：

```powershell
# 进入项目目录
cd C:\AegisOS

# 初始化 Git 仓库
git init

# 配置 Git 用户名（替换为你的信息）
git config user.email "your-email@example.com"
git config user.name "Your Name"

# 检查状态
git status
```

---

## 第三步：添加文件到 Git

```powershell
# 添加所有文件到暂存区
git add .

# 检查已添加的文件
git status
```

---

## 第四步：创建首次提交

```powershell
# 创建提交
git commit -m "Initial commit: AegisOS v1.0 MVP

A controlled AI agent scheduling platform with:
- Budget control ($5/day default) with token tracking
- Rate limiting (5 tasks/min with sliding window)
- Governance compliance (AI proposes, human approves)
- Governed optimization (Phase 6 - shadow execution)
- Version switching with rollback capability
- Discord integration with slash commands

Safety features:
- No hardcoded secrets (environment variables only)
- No auto-execution (human approval required)
- No auto-switching (manual trigger only)
- Shadow validation before production

Phase 1-6 complete with 3 contract layers implemented."
```

---

## 第五步：推送到 GitHub

```powershell
# 添加远程仓库（替换为你的用户名）
git remote add origin https://github.com/你的用户名/AegisOS.git

# 创建 main 分支
git branch -M main

# 推送到 GitHub
git push -u origin main
```

输入 GitHub 用户名和密码/Token（如果提示）。

---

## 第六步：验证发布

### 6.1 在浏览器中打开
```
https://github.com/你的用户名/AegisOS
```

### 6.2 检查以下内容
- [ ] README.md 正确显示
- [ ] 文件列表完整（没有敏感文件）
- [ ] LICENSE 显示 MIT
- [ ] 没有 .db 文件
- [ ] 没有 __pycache__ 目录

---

## 完整命令汇总

```powershell
# 第1步：进入目录
cd C:\AegisOS

# 第2步：初始化
git init
git config user.email "your@email.com"
git config user.name "Your Name"

# 第3步：添加文件
git add .

# 第4步：提交
git commit -m "Initial commit: AegisOS v1.0 MVP"

# 第5步：推送
git remote add origin https://github.com/你的用户名/AegisOS.git
git branch -M main
git push -u origin main
```

---

## 常见问题

### Q1: 提示 "git 不是内部或外部命令"
**解决**: Git 未安装或不在 PATH 中
1. 下载安装: https://git-scm.com/download/win
2. 重启 PowerShell/CMD
3. 重新尝试

### Q2: 推送时提示认证失败
**解决**: 需要使用 Personal Access Token
1. 访问 https://github.com/settings/tokens
2. 点击 **Generate new token (classic)**
3. 勾选 `repo` 权限
4. 生成后复制 token
5. 推送时输入 token 作为密码

### Q3: 提示 "failed to push some refs"
**解决**: 远程仓库有冲突
```powershell
git pull origin main --rebase
git push origin main
```

### Q4: 不小心提交了敏感信息
**解决**: 需要移除并强制推送
```powershell
# 从提交历史中移除文件
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch 文件名" HEAD

# 强制推送
git push origin main --force
```

---

## 发布后的设置

### 添加 Topics（标签）
在 GitHub 仓库页面 → 点击右侧齿轮 → 添加 topics：
```
ai-agent, task-scheduler, governance, discord-bot, budget-control, python
```

### 启用 Issues
Settings → General → Issues → ✅ 勾选

### 启用 Discussions（可选）
Settings → General → Discussions → ✅ 勾选

---

## 后续更新流程

```powershell
cd C:\AegisOS

# 查看修改
git status

# 添加修改的文件
git add 文件名
# 或添加所有
git add .

# 提交
git commit -m "描述你的修改"

# 推送
git push origin main
```

---

## 验证清单

发布完成后，在 GitHub 页面确认：

- [ ] 能看到 README.md 内容
- [ ] 能看到 10 个 .md 文档
- [ ] 能看到 LICENSE 文件
- [ ] 能看到 aegisos/ 代码目录
- [ ] 没有 aegisos.db 文件
- [ ] 没有 logs/ 目录内容
- [ ] 没有 __pycache__ 目录
- [ ] config.yaml 中 token 为空

---

**恭喜！AegisOS 已成功发布到 GitHub！** 🎉
