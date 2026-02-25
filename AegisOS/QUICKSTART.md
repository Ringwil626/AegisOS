# AegisOS 快速入门指南

## 1. 安装与启动

```bash
# 进入项目目录
cd AegisOS

# 启动 CLI 模式（推荐新手使用）
./start.sh --cli
```

第一次运行会自动：
- 创建 Python 虚拟环境
- 安装依赖
- 创建必要的目录
- 初始化数据库

## 2. CLI 交互模式

启动后你会看到提示符 `aegisos>`，可以输入以下命令：

### 基础命令
```
aegisos> status     # 查看系统状态
aegisos> wake       # 启动系统（开始处理任务）
aegisos> stop       # 停止系统
```

### 创建任务
```
# 普通任务
aegisos> task echo hello world

# AI 任务（使用 mock AI，无需 API key）
aegisos> task ai: 解释什么是确定性执行

# Kimi 任务（需要 MOONSHOT_API_KEY）
aegisos> task kimi: 分析这段代码的问题
```

### 进化提案
```
aegisos> evolve "添加任务优先级功能"
```

### 退出
```
aegisos> exit
```

## 3. 启用真实 AI

```bash
# 设置环境变量
export MOONSHOT_API_KEY="sk-your-key-here"

# 重新启动
./start.sh --cli
```

## 4. 运行模式对比

| 模式 | 命令 | 适用场景 |
|------|------|----------|
| CLI | `./start.sh --cli` | 本地开发、测试 |
| Demo | `./start.sh --demo` | 快速体验功能 |
| 后台 | `./start.sh --no-discord` | 服务器部署 |
| 完整 | `./start.sh` | 需要 Discord 集成 |

## 5. 检查系统健康

```bash
# 运行测试套件
python test_all.py
```

## 6. 常见问题

### Q: 提示 "Another instance is already running"
A: 删除锁文件：`rm aegisos.lock`，然后重试。

### Q: 如何查看任务执行结果？
A: 在 CLI 模式下，任务执行后会自动显示结果。也可以通过数据库查看：
```bash
sqlite3 aegisos.db "SELECT * FROM tasks ORDER BY id DESC LIMIT 5;"
```

### Q: 预算超了怎么办？
A: 编辑 `config.yaml` 调整预算限制，或等待下一周期重置。

## 7. 下一步

- 阅读 [README.md](README.md) 了解完整功能
- 查看 [GOVERNANCE.md](GOVERNANCE.md) 了解架构设计
- 探索 `aegisos/` 目录下的源码
