# 切换 GitHub 账号完整指南

## 情况一：只改本地提交信息（刚刚的提交）

如果只想修改刚才那条提交的作者信息：

```powershell
# 修改最后一条提交的作者信息
git commit --amend --author="新用户名 <新邮箱@example.com>"

# 然后强制推送（如果已经推送到远程）
git push origin main --force-with-lease
```

---

## 情况二：切换到另一个 GitHub 账号

### 步骤 1：修改 Git 配置

```powershell
# 查看当前配置
git config user.name
git config user.email

# 修改为新账号信息
git config user.name "新用户名"
git config user.email "新邮箱@example.com"

# 验证修改
git config user.name
git config user.email
```

### 步骤 2：修改远程仓库地址

```powershell
# 查看当前远程地址
git remote -v

# 删除旧的远程关联
git remote remove origin

# 添加新的远程仓库（新账号的仓库地址）
git remote add origin https://github.com/新用户名/AegisOS.git

# 验证
git remote -v
```

### 步骤 3：推送到新账号

```powershell
# 推送
git push -u origin main

# 如果需要，输入新账号的 Personal Access Token 作为密码
```

---

## 情况三：完全重新开始（推荐）

如果想彻底切换到另一个 GitHub 账号，最干净的方法是：

```powershell
# 1. 删除本地 .git 目录
Remove-Item -Recurse -Force C:\AegisOS\.git

# 2. 在 GitHub 上用新账号创建仓库
# 访问 https://github.com/new
# 仓库名：AegisOS

# 3. 重新初始化
cd C:\AegisOS
git init
git config user.name "新用户名"
git config user.email "新邮箱@example.com"
git add .
git commit -m "Initial commit: AegisOS v1.0 MVP"
git remote add origin https://github.com/新用户名/AegisOS.git
git branch -M main
git push -u origin main
```

---

## 情况四：同一台电脑管理多个 GitHub 账号

### 方法 A：使用不同的仓库目录

```powershell
# 账号1的项目
cd C:\GitHub\账号1\AegisOS
git config user.name "账号1"
git config user.email "账号1@example.com"

# 账号2的项目
cd C:\GitHub\账号2\AegisOS
git config user.name "账号2"
git config user.email "账号2@example.com"
```

### 方法 B：使用 SSH Key（高级）

```powershell
# 1. 生成两个 SSH Key
ssh-keygen -t ed25519 -C "账号1@example.com" -f ~/.ssh/id_ed25519_account1
ssh-keygen -t ed25519 -C "账号2@example.com" -f ~/.ssh/id_ed25519_account2

# 2. 添加到 SSH Agent
ssh-add ~/.ssh/id_ed25519_account1
ssh-add ~/.ssh/id_ed25519_account2

# 3. 在 GitHub 上添加对应的 Public Key

# 4. 配置 SSH Config
notepad ~/.ssh/config
```

SSH Config 内容：
```
# 账号1
Host github-account1
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_account1

# 账号2
Host github-account2
    HostName github.com
    User git
    IdentityFile ~/.ssh/id_ed25519_account2
```

使用：
```powershell
# 账号1的项目
git remote set-url origin git@github-account1:账号1/AegisOS.git

# 账号2的项目
git remote set-url origin git@github-account2:账号2/AegisOS.git
```

---

## 快速解决方案（针对你的情况）

你刚才的提交使用了默认的 `Ringwil Chan <chanr@china.hamiltonbeach.com.cn>`。

### 方案 A：只改作者信息（推荐）

```powershell
cd C:\AegisOS

# 修改最后一条提交
git commit --amend --author="你的GitHub用户名 <你的邮箱@example.com>" --no-edit

# 如果已推送，强制更新
git push origin main --force-with-lease
```

### 方案 B：重新开始到新账号

```powershell
cd C:\AegisOS

# 1. 删除本地 git 历史
Remove-Item -Recurse -Force .git

# 2. 在 GitHub 上用新账号创建仓库
# 访问 https://github.com/new，创建 AegisOS 仓库

# 3. 重新初始化并推送
git init
git config user.name "你的GitHub用户名"
git config user.email "你的邮箱@example.com"
git add .
git commit -m "Initial commit: AegisOS v1.0 MVP"
git remote add origin https://github.com/你的新用户名/AegisOS.git
git branch -M main
git push -u origin main
```

---

## 验证切换成功

```powershell
# 查看本地配置
git config user.name
git config user.email

# 查看远程仓库
git remote -v

# 查看提交历史
git log --oneline -5

# 在浏览器中验证
start https://github.com/你的用户名/AegisOS
```

---

## 注意事项

⚠️ **强制推送风险**
- `git push --force` 会覆盖远程历史
- 如果多人协作，会丢失他人提交
- 单人项目可以安全使用

⚠️ **提交信息不可更改**
- 已经推送到远程的提交，修改作者后需要强制推送
- GitHub 上的贡献统计基于提交邮箱

✅ **推荐做法**
- 个人项目：直接强制推送
- 团队项目：不要修改已推送的提交
