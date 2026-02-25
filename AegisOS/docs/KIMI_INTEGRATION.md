# AegisOS × Kimi API 集成指南

本文档详细说明如何将 Kimi API 接入 AegisOS，以及系统在设计上如何支持扩展性。

---

## 1️⃣ Kimi API 接入详细步骤

### Step 1：准备 Kimi API 客户端

AegisOS 提供封装好的 `kimi_client.py` 模块，统一调用 Kimi API：

```python
from aegisos.ai.kimi_client import KimiClient, check_configuration

# 初始化（从环境变量读取配置）
client = KimiClient()

# 检查配置
ok, msg = check_configuration()
print(msg)  # Kimi client ready: model=kimi-k2.5, ...

# 执行任务
result = client.run_task(
    prompt="Refactor error handling",
    context={
        "project_name": "my_project",
        "agent_md": "./agent.md",
        "priority": "high"
    }
)

# 结果是 JSON Action Schema
# {
#   "actions": [...],
#   "explanation": "...",
#   "risk_level": "low"
# }
```

**关键点**：
- 所有任务都通过 `run_task()` 发给 Kimi API
- 结果必须是 **JSON Action Schema**，防止 AI 输出不规范
- 支持自动重试（RateLimit 指数退避）

---

### Step 2：项目上下文封装

AegisOS 为每个项目维护：
- `agent.md`（角色/指令模板）
- 历史修改索引 `history/`
- 项目描述文件 `project_desc.md`

**封装成 prompt**：

```python
context = {
    "project_name": "AegisOS",
    "agent_md": "/path/to/agent.md",
    "history_index": "/path/to/history/",
    "project_desc": "/path/to/project_desc.md",
    "memory": ["prev_task_1", "prev_task_2"],  # 相关历史记忆
    "priority": "high",                        # 任务优先级
    "token_quota": 50000,                      # 剩余 token 配额
    "shadow_run": False                        # 是否影子运行
}

prompt = "Refactor the error handling module"
result = client.run_task(prompt, context=context)
```

**扩展性**：你可以在 context 中自由添加字段：
- `memory`：工程记忆
- `priority`：任务优先级
- `deadline`：截止时间
- `shadow_run`：影子运行模式
- `user_quota`：用户配额

---

### Step 3：任务提交与数据库绑定

在 AegisOS 中，每个调用 Kimi API 的任务都必须写入 SQLite：

```python
from aegisos.db.sqlite_store import create_task, update_task_status

# 1. 创建任务记录
task_id = create_task(
    project="my_project",
    intent="refactor_error_handling",
    raw_command=prompt,
    task_type="kimi_api"
)

# 2. 执行任务
try:
    update_task_status(task_id, "running")
    
    # 调用 Kimi API（受 Budget Guard 保护）
    response = client.run_task(prompt, context)
    
    # 存储结果
    update_task_status(task_id, "completed")
    
except Exception as e:
    update_task_status(task_id, "failed")
    raise
```

**保证连续性**：
- 每个项目的上下文与任务在 DB 中是连续的
- Crash 后可以恢复 running 任务

**扩展性**：可以在 `tasks` 表增加字段：
- `priority`：任务优先级
- `deadline`：截止时间
- `shadow_run`：是否为影子运行
- `estimated_cost`：预估成本

---

### Step 4：结果处理（JSON Action Schema）

Kimi API 返回的是 **JSON Action Schema**：

```json
{
  "actions": [
    {"type": "edit_file", "file": "aegisos/core/supervisor.py", "content": "..."},
    {"type": "create_file", "file": "tests/test_supervisor.py", "content": "..."},
    {"type": "update_memory", "key": "error_handling_pattern", "value": "..."},
    {"type": "shell_command", "command": "python -m pytest tests/", "timeout": 60}
  ],
  "explanation": "Added try-except blocks and logging",
  "risk_level": "medium"
}
```

**AegisOS 的 Executor 会按 schema 安全执行**：

```python
# executor/task_runner.py 中的处理逻辑
def execute_actions(actions: list) -> bool:
    for action in actions:
        action_type = action.get("type")
        
        if action_type == "edit_file":
            # 验证路径安全后才执行
            safe_edit_file(action["file"], action["content"])
        
        elif action_type == "shell_command":
            # 限制命令范围和超时
            safe_shell_command(action["command"], timeout=action.get("timeout", 30))
        
        elif action_type == "update_memory":
            # 写入工程记忆
            record_memory(action["key"], action["value"])
        
        # ... 其他 action 类型
```

**防止 AI 直接写文件或执行危险命令**：
- 路径白名单检查
- 命令黑名单检查
- 沙箱目录限制

---

### Step 5：监控 & Heartbeat

每个任务完成后写 heartbeat：

```python
from aegisos.db.sqlite_store import write_heartbeat

# 任务完成后
write_heartbeat(
    component="executor",
    message=f"Task {task_id} completed",
    runtime_version="v1.0"
)
```

**如果任务超时或 API 调用失败**：
- 自动重置任务为 `pending`
- Supervisor 检测到后重新调度
- 超过重试次数后标记为 `failed`

---

## 2️⃣ AegisOS 扩展性设计

AegisOS 在设计 Kimi API 接入时考虑了以下扩展性：

### 1. 项目隔离

```
projects/
├── project_a/
│   ├── agent.md           # 项目A的专属指令
│   ├── project_desc.md    # 项目A的描述
│   └── history/           # 项目A的修改历史
├── project_b/
│   ├── agent.md           # 项目B的专属指令
│   ├── project_desc.md
│   └── history/
```

- 每个项目有独立目录和上下文
- 多项目可以共存，互不干扰
- 任务队列按项目隔离

---

### 2. 任务队列通用化

**Executor 不关心任务来源**（CLI 或 API），只执行 **JSON Action Schema**：

```python
# 来源可以是：
source_a = "/task refactor this"                    # Discord 命令
source_b = client.run_task("refactor this")         # Kimi API
source_c = other_ai_client.execute("refactor")      # 其他 AI 系统

# Executor 统一处理
execute_actions(result["actions"])  # 相同的执行逻辑
```

**可以未来接入其他 AI 系统**，只要输出相同 schema：
- GPT-4 / Claude / Gemini
- 本地模型（Llama、Qwen）
- 自定义模型

---

### 3. 上下文可扩展

`context` 字典可以自由扩展，不影响现有执行逻辑：

```python
# 基础上下文
context = {
    "project_name": "...",
    "agent_md": "...",
}

# 扩展：增加优先级
context["priority"] = "critical"

# 扩展：增加 token 限额
context["token_quota"] = 50000

# 扩展：增加影子运行标记
context["shadow_run"] = True

# 扩展：增加用户权限
context["user_role"] = "admin"  # or "guest"

# 所有扩展都会自动包含在 prompt 中
```

---

### 4. 安全沙箱

**Executor 对 schema 做严格检查**：

```python
FORBIDDEN_PATHS = [
    "../",                      # 目录遍历
    "/etc/", "/root/",          # 系统目录
    "aegisos/ai/ledger.py",     # 核心模块
    "aegisos/db/sqlite_store.py",
]

FORBIDDEN_COMMANDS = [
    "rm -rf", "dd", "mkfs",     # 危险命令
    "curl | bash",              # 远程执行
]

def validate_action(action: dict) -> bool:
    """验证 action 是否安全"""
    if action["type"] == "edit_file":
        if any(p in action["file"] for p in FORBIDDEN_PATHS):
            return False
    
    if action["type"] == "shell_command":
        if any(c in action["command"] for c in FORBIDDEN_COMMANDS):
            return False
    
    return True
```

**防止 AI 越权**：
- 禁止修改 Budget/Ledger 相关代码
- 禁止修改数据库核心表
- 禁止执行高危系统命令

---

### 5. 版本切换 / Shadow Run 支持

每个项目 API 调用都可以选择在 shadow 版本中运行：

```python
# 正常执行（影响生产）
context = {"shadow_run": False}
result = client.run_task(prompt, context)
# 修改直接应用到 runtime/

# Shadow 执行（隔离验证）
context = {"shadow_run": True}
result = client.run_task(prompt, context)
# 修改应用到 runtime_shadow/
# 验证通过后再同步到 runtime/
```

**不影响生产任务**：
- Shadow 环境与生产完全隔离
- 可以并行运行多个 shadow 测试
- 失败不影响生产稳定性

---

### 6. 多模型扩展

你可以在 `kimi_client.py` 基础上增加多模型路由：

```python
class MultiModelClient:
    """路由到不同模型 based on 任务复杂度"""
    
    MODELS = {
        "kimi-k2.5": KimiClient(),      # 大模型，结构性改动
        "kimi-k2-turbo": KimiClient(model="kimi-k2-turbo"),  # 快速响应
        "local-llama": LocalClient(),    # 本地模型，简单任务
    }
    
    def route_task(self, prompt: str, complexity: str) -> dict:
        if complexity == "high":
            return self.MODELS["kimi-k2.5"].run_task(prompt)
        elif complexity == "low":
            return self.MODELS["local-llama"].run_task(prompt)
        else:
            return self.MODELS["kimi-k2-turbo"].run_task(prompt)
```

**模型选择策略**：
- 小模型做小改动（命名、格式）
- 大模型做结构性 evolve（重构、架构）
- 本地模型处理敏感数据

---

## 3️⃣ 快速启动

### 环境配置

```powershell
# 必需
$env:MOONSHOT_API_KEY="sk-your-kimi-api-key"
$env:DISCORD_TOKEN="your-discord-bot-token"

# 可选
$env:MOONSHOT_MODEL="kimi-k2.5"
$env:MOONSHOT_MAX_TOKENS="4000"
```

### 启动脚本

```python
# run_kimi.py
from aegisos.ai.kimi_client import kimi_call, check_configuration
import aegisos.ai.executor as executor
import aegisos.executor.task_runner as task_runner

# 检查配置
ok, msg = check_configuration()
if not ok:
    raise RuntimeError(msg)
print(f"✅ {msg}")

# 注入 Kimi 客户端
executor.mock_ai_call = kimi_call
task_runner.mock_ai_call = kimi_call

# 启动系统
from main import main
main()
```

### 运行

```powershell
python run_kimi.py
```

---

## 4️⃣ 验证集成

1. **Discord 命令测试**：
   ```
   /task ai: Add error handling to task runner
   ```

2. **检查 Budget 记录**：
   ```sql
   SELECT * FROM ai_ledger ORDER BY id DESC LIMIT 1;
   ```

3. **检查任务执行**：
   ```sql
   SELECT * FROM tasks WHERE type='ai' ORDER BY id DESC LIMIT 1;
   ```

---

## 附录：JSON Action Schema 规范

```typescript
interface ActionSchema {
  actions: Action[];
  explanation: string;
  risk_level: "low" | "medium" | "high";
}

type Action = 
  | { type: "edit_file"; file: string; content: string }
  | { type: "create_file"; file: string; content: string }
  | { type: "delete_file"; file: string }
  | { type: "update_memory"; key: string; value: string }
  | { type: "shell_command"; command: string; timeout: number }
  | { type: "log_message"; level: string; message: string };
```
