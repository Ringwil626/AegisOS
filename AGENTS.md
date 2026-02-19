# AegisOS - Agent Guidance Document

## 项目阶段声明

**AegisOS v1.0 已完成 Build Phase（构建期）**

> ✅ 系统"能稳定运行并受控演化"
> 
> 🚧 即将进入 Operational Phase（运行治理期）

---

## 1. 系统概述

AegisOS 是一个具备**自演化能力**的 AI Agent 控制系统。与传统软件不同，它没有"最终版本"概念，而是持续存在的生命体。

### 1.1 核心设计哲学

```
传统软件：开发 → 发布 → 维护 → 退役
AegisOS：诞生 → 演化 → 治理 → 再训练 → 持续
```

**关键认知转变**：
- ❌ 不是"开发一个系统"
- ✅ 而是"运营一个会写代码的实体"

---

## 2. Build Phase（构建期）✅ 已完成

### 2.1 已交付阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | Runtime Skeleton - 基础运行时框架 | ✅ |
| Phase 2 | Task Queue - 任务队列系统 | ✅ |
| Phase 3 | Executor - 任务执行器 | ✅ |
| Phase 4 | Supervisor 调度 - 执行权限边界 | ✅ |
| Phase 5 | AI 接入与 Ledger - 成本治理 | ✅ |
| Phase 6 | Version Evolution - 受控自我演化 | ✅ |
| Phase 7 | Engineering Memory - 工程记忆系统 | ✅ |
| Hardening | Production 加固 - P0-P5 生产级保障 | ✅ |

### 2.2 Build Phase 交付物

```
aegisos/
├── core/               # Supervisor, Health, Backup, Instance Lock
├── db/                 # SQLite 存储层 (WAL mode)
├── executor/           # 任务执行器
├── ai/                 # AI Ledger (预算控制)
├── evolution/          # 进化管理 + 验证器
├── memory/             # 工程记忆 (检索 + 向量索引)
└── interfaces/         # Discord Bot 控制接口

main.py                 # 入口 (集成所有 Phase)
RUNBOOK.md              # 运维操作手册
config.yaml             # 系统配置
```

### 2.3 Build Phase 安全架构

```
┌─────────────────────────────────────────────────────────┐
│                    AegisOS Runtime                       │
├─────────────────────────────────────────────────────────┤
│  Supervisor (心跳) ←→ Main Loop (门控) ←→ Executor       │
│       ↑                                        ↓        │
│  Health Check                               AI Ledger   │
│       ↑                                    (预算守卫)    │
│  Instance Lock                                  ↓       │
│  (防双开)                                   AI 调用     │
│                                                   ↓     │
│  Evolution Manager (隔离区) ←→ Validator ←→ 提案生成    │
│       ↓                                                 │
│  Engineering Memory (经验学习)                          │
└─────────────────────────────────────────────────────────┘

约束:
- AI 不能直接修改 runtime
- AI 不能绕过 ledger
- AI 不能写 memory 记录 (只能系统写)
- Evolution 必须通过隔离区验证
```

---

## 3. Operational Phase（运行治理期）🚧 进行中

### 3.1 范式转变

| Build Phase | Operational Phase |
|-------------|-------------------|
| "造出系统" | "治理实体" |
| 功能开发 | 策略调优 |
| 验证正确性 | 控制熵增 |
| 一次性的 | 持续循环的 |

### 3.2 三大治理循环

#### 🔁 Loop 1: 运行治理 (Operational Governance)

**目标**: 防止系统半年后变得不可解释

| 治理项 | 说明 | 频率 |
|--------|------|------|
| Token 预算策略调整 | 根据实际成本结构调整限制 | 每周 |
| Memory 污染清理 | 删除过时/噪声记忆 | 每月 |
| Evolution 质量审计 | 分析演化成功/失败率 | 每次演化后 |
| 野心范围控制 | 限制 AI 可修改的模块范围 | 按需 |
| 版本冻结 | 定期保存稳定快照 | 每版本 |

#### 🔁 Loop 2: 能力扩展 (Capability Phases)

**目标**: 按需增强系统能力

| Phase | 内容 | 优先级 |
|-------|------|--------|
| Phase 8 | Multi-project Routing - 多工程管理 | 待定 |
| Phase 9 | Tool Sandboxing - 工具链沙盒 | 待定 |
| Phase 10 | Simulation Environment - 预上线沙盒 | 待定 |
| Phase 11 | Policy Engine - 模块级修改策略 | 待定 |
| Phase 12 | Explainability Layer - 变更理由报告 | 待定 |
| Phase 13 | Human Approval Gates - 高风险人工审批 | 待定 |

> ⚠️ **注意**: 这些不是必须的，根据实际需求决定添加

#### 🔁 Loop 3: 熵增控制 (Entropy Control)

**目标**: 应对系统老化

```
长期运行必然发生:
├── Memory 变噪声 → 需要再蒸馏
├── Evolution 保守/激进失衡 → 需要策略重写
├── Schema 积累技术债 → 需要迁移
├── Token 成本结构改变 → 需要预算重平衡
└── 整体熵增 → 需要 Second-Order Engineering
```

**应对措施**:
- 系统再训练 (规则重调优，不是模型重训练)
- Memory 蒸馏 (保留精华，丢弃噪声)
- 策略重写 (基于审计数据)
- 版本归档 (历史版本留存)

---

## 4. 技术架构

### 4.1 运行时组件

```python
# 核心约束
Supervisor:     永不接触 tasks/ledger
Main Loop:      唯一调度点，10s tick
Executor:       被动工具，不感知状态
AI Ledger:      所有 AI 调用必须记录
Evolution:      只写 proposals/，不碰 runtime
Validator:      零 AI 消耗，纯测试
```

### 4.1a Inference Contract v1.0 (Kimi API Integration)

Kimi API 作为受控算力层的接入规范：

```
AegisOS Inference Flow:
  Supervisor
     ↓
  Fetch pending task
     ↓
  InferenceExecutor.execute()
     ↓
  ┌─────────────────────────────────────┐
  │ 1. StateBuilder.build_prompt()      │
  │ 2. Budget Check (Phase5)            │
  │ 3. kimi_client.run_inference()      │ ← Stateless
  │ 4. Validator.validate()             │
  │ 5. UsageLogger.log_inference_usage()│ → ai_ledger
  └─────────────────────────────────────┘
     ↓
  Mark task complete
```

**Inference Contract 设计原则：**
- `infra/kimi_client.py`: 无状态推理执行器（不是 SDK 封装）
- `core/state_builder.py`: Prompt 构造责任（与执行分离）
- `core/validator.py`: AI 输出校验（安全门）
- `audit/usage_logger.py`: 成本审计（Phase5 唯一数据来源）

**核心约束：**
- Kimi 无状态：每次调用带 task_id，不缓存
- 完全结构化：InferenceRequest → InferenceResult
- 可审计：返回 usage（prompt/completion/total tokens）
- 可重试：指数退避，仅对 timeout/5xx 重试
- 可超时：外层强制 timeout_sec 中断

详见：`INFERENCE_CONTRACT.md`

### 4.1b Prompt Contract v1.0 (Machine Contract)

将 Prompt 定义为**系统调用协议**，而非聊天消息：

**核心转变：**
- ❌ AI 是助手（可以解释、建议、发挥）
- ✅ AI 是执行引擎（只能按 Schema 返回）

**Contract 结构（5 区块，顺序不可变）：**
```
[SYSTEM_ROLE]       → 定义模型身份（执行引擎，不是助手）
[EXECUTION_RULES]   → 硬约束（禁止解释、建议、发挥）
[CONTEXT_STATE]     → 客观状态（项目、运行时、环境）
[TASK_DEFINITION]   → 结构化 Action + Inputs
[OUTPUT_SCHEMA]     → 强制 AI 服从的 JSON Schema
```

**输出 Schema（必须严格遵守）：**
```json
{
  "status": "success | failure",
  "prompt_version": "1.0",
  "artifacts": [{"type": "...", "path": "...", "content": "..."}],
  "errors": [{"code": "...", "message": "..."}],
  "metrics": {"confidence": "high | medium | low"}
}
```

**验证规则：**
- 所有字段必须存在
- 不允许额外字段
- 版本必须匹配 `"1.0"`
- 失败时必须提供 errors 数组

**Action 白名单：**
- `create_file`, `modify_file`, `delete_file`
- `run_test`, `analyze_code`, `generate_patch`

**Protocol Violation 处理：**
- 任务立即标记为失败
- 错误代码：`AI_PROTOCOL_VIOLATION`
- 需要人工审查

详见：`PROMPT_CONTRACT.md`

### 4.1c Executor Contract v1.0 (Task State Machine Driver)

Executor 从"AI 调用器"转变为**任务状态机执行器**：

**三层隔离架构：**
```
Supervisor (Lifecycle Controller)
    ↓ 调用
Executor (State Machine Driver)  ← 短生命周期，单次执行
    ↓ 调用
AI (Untrusted Compute Node)      ← 无状态推理
```

**状态机（严格三态）：**
```
pending → running → completed
               ↘
                failed
```

**禁止状态：**
- ❌ `retrying`, `waiting_ai`, `thinking`, `partial_done`

**执行步骤（严格顺序）：**
1. Cleanup stuck tasks（超时回收）
2. Claim pending task（原子领取）
3. Build Prompt Contract
4. Run inference
5. Validate output
6. Apply artifacts（机械写入）
7. Mark completed OR failed

**并发控制：**
- 原子 claim：`UPDATE ... WHERE id = (SELECT ...)`
- 防止多 Executor 竞争

**超时恢复：**
- `TIMEOUT_WINDOW = 300s`
- 启动时重置 stuck running tasks 到 pending
- 系统自愈合

**成功判定（极其严格）：**
```
inference_success AND schema_valid AND artifacts_applied
```

**否则一律 `failed`。**

**审计记录：**
- `execution_log` 表记录每次执行
- 包含：task_id, started_at, finished_at, success, tokens_used, latency_ms
- 用于 Phase5 成本分析

详见：`EXECUTOR_CONTRACT.md`

### 4.1d Phase5 AI Usage Accounting（用量治理层）

Phase5 将 AI 转变为**可预算、可限流、可审计的基础设施资源**：

**核心组件：**

```
┌─────────────────────────────────────────┐
│  Budget Gate（预算闸门）                 │
│  - 执行前检查 budget                     │
│  - 执行前检查 rate_limit                 │
│  - 超预算 → HARD STOP（不是告警）        │
├─────────────────────────────────────────┤
│  usage_ledger（用量账本）                │
│  - 任务级记账（不是调用级）              │
│  - Project 维度归因                      │
│  - 即时成本计算                          │
├─────────────────────────────────────────┤
│  pricing（定价表）                       │
│  - 本地 YAML（不请求在线价格）           │
│  - 确定性计算                            │
│  - 支持多 provider                       │
└─────────────────────────────────────────┘
```

**数据库表：**

| 表 | 用途 |
|----|------|
| `usage_ledger` | AI 用量记录（SSOT） |
| `budgets` | 项目预算配置 |
| `rate_limit_log` | 滑动窗口速率限制 |

**默认预算：**

| Project | Daily Token | Daily Cost | Rate Limit |
|---------|-------------|------------|------------|
| aegisos | 100,000 | $5.00 | 5/min |
| default | 50,000 | $2.00 | 3/min |

**Discord 查询：**
- `/usage today [project]` - 今日用量
- `/usage by_project` - 多项目对比
- `/budget status [project]` - 预算状态

**自进化基础：**
Phase5 为自进化提供**观察自己行为的数据基础**：
- 自动选择更便宜模型
- 识别高失败 Prompt
- 自动拆分大任务
- 调整执行节奏

详见：`PHASE5_USAGE_ACCOUNTING.md`

### 4.1d Phase6 Governed Optimization（受监管的自进化）

Phase6 建立**受监管的优化闭环**，让系统从"可控自动化"迈向"可管理自进化"。

**核心原则：**
- 离线决策 + 在线执行（不是实时学习）
- AI 提建议 → 系统验证 → 人类批准 → 切换版本
- 永远不允许偷偷升级自己

**四层隔离架构（参谋部模式）：**

```
┌─────────────────────────────────────────┐
│  Intelligence Layer (参谋部)             │
│  - analyzer: 只读数据，提取指标          │
│  - evaluator: 判断是否值得优化           │
│  - optimizer: 生成提案（不直接改系统）   │
│  - policy: 策略版本化 + 影子执行         │
│                                         │
│  关键：这层不参与任务执行，只读数据      │
└─────────────────────────────────────────┘
                   ↓ 生成 Proposal
┌─────────────────────────────────────────┐
│  Approval Gate                          │
│  /proposals approve <id>               │
│  必须显式批准                           │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│  Shadow Execution (影子验证)            │
│  - 新旧策略并行执行                     │
│  - 只比较指标，不影响生产               │
│  - 无 regression 才能通过               │
└─────────────────────────────────────────┘
                   ↓ 验证通过
┌─────────────────────────────────────────┐
│  /switch strategy_version=<id>          │
│  - 激活新版本                           │
│  - 旧版本 retired                       │
│  - 60分钟监控期（可回滚）               │
└─────────────────────────────────────────┘
```

**分析指标（4个关键指标）：**

| 指标 | 检测问题 |
|------|----------|
| 成功率趋势 | Prompt 或任务结构退化 |
| Token 消耗异常 | Prompt 冗余、上下文污染 |
| 重试率 | 指令不清晰 |
| 延迟分布 | 任务粒度过大 |

**提案类型：**
- `prompt_tuning` - 优化 Prompt 模板
- `task_split` - 拆分大任务
- `model_switch` - 切换模型
- `context_compression` - 压缩上下文

**策略版本状态：**
```
PENDING → APPROVED → SHADOW → ACTIVE
              ↓           ↓
           REJECTED   (验证失败)
```

**Discord 命令：**
```
/proposals list              - 列出提案
/proposals inspect <id>      - 查看详情
/proposals approve <id>      - 批准提案
/switch strategy_version=<id> - 切换策略
```

**安全机制：**
- ❌ 不自动执行（必须人工批准）
- ❌ 不实时学习（离线决策）
- ✅ Shadow 验证（不影响生产）
- ✅ 版本化管理（可回滚）
- ✅ 监控期（自动回滚）

**哲学：**
> AegisOS 不是 AI 自动改代码，
> 而是 AI 提出运营建议，
> 系统用工程流程验证这些建议。

详见：`PHASE6_GOVERNED_OPTIMIZATION.md`

### 4.2 状态机

```
System State:
  initialized → running ↔ stopped
  
Task State:
  pending → running → completed/failed
  
Evolution State:
  proposed → validated → approved → deployed
       ↓
     rejected
```

### 4.3 数据库 Schema (Runtime Transition Protocol v1.0)

| 表 | 用途 | 所属 Phase |
|----|------|-----------|
| tasks | 任务队列 | P2 |
| system_state | 系统状态 | P1 |
| heartbeats | 健康检查 | P4 |
| ai_ledger | AI 成本审计 | P5 |
| ai_budget | 预算配置 | P5 |
| **usage_ledger** | **AI 用量记录（SSOT）** | **P5** |
| **budgets** | **项目预算配置** | **P5** |
| **rate_limit_log** | **速率限制日志** | **P5** |
| evolution_jobs | 进化提案 | P6 |
| **proposals** | **优化提案** | **P6** |
| **strategy_versions** | **策略版本** | **P6** |
| engineering_memory | 工程记忆 | P7 |
| audit_log | 审计日志 | Hardening |
| runtime_health_snapshot | 健康快照 | Hardening |
| execution_log | 执行审计日志 | P4 |

---

## 5. 安全红线

### 5.1 AI 治理红线

**绝对禁止**:
- 修改 `ai/ledger.py` 让 AI 调用绕过记录
- 在 `validator.py` 中添加 AI 调用
- 直接修改 `runtime/` 目录（应通过 evolution）
- 删除或篡改 `ai_ledger` 记录

### 5.2 审批流程

```
/evolve → AI 生成提案 → /approve → 人工审核 → /switch 部署
```

---

## 6. 运营指南

### 6.1 日常检查清单

```sql
-- 每日 AI 财务日报
SELECT 
    DATE(created_at, 'unixepoch') as day,
    COUNT(*) as calls,
    SUM(total_tokens) as tokens,
    SUM(estimated_cost) as cost,
    SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as blocked
FROM ai_ledger
GROUP BY day
ORDER BY day DESC;

-- 每周记忆健康度
SELECT COUNT(*) as total_memories,
       AVG(CASE WHEN outcome='success' THEN 1 ELSE 0 END) as success_rate
FROM engineering_memory
WHERE created_at > unixepoch() - 604800;
```

### 6.2 启动命令

```bash
# 设置 Discord Token
$env:DISCORD_TOKEN="your-token-here"

# 启动系统
python main.py
```

### 6.3 优雅停止

```
# 在运行窗口按 Ctrl+C 一次
# 或使用 Discord 命令
/stop
```

---

## 7. 文档索引

| 文档 | 用途 |
|------|------|
| `AGENTS.md` | 本文件 - 架构概述与阶段说明 |
| `RUNBOOK.md` | 运维操作手册 - 具体命令操作指南 |
| `OPERATIONS.md` | 运营治理层 - 可执行的规则与流程 |
| `config.yaml` | 系统配置 |

### 文档使用场景

```
新加入的开发者/AI:
  1. 先看 AGENTS.md 理解整体架构
  2. 再看 OPERATIONS.md 理解治理规则
  3. 需要具体操作时查 RUNBOOK.md

日常运营:
  - AI 执行自动化: 按 OPERATIONS.md 的清单执行
  - 人工干预: 查 RUNBOOK.md 具体操作步骤
  - 架构决策: 参考 AGENTS.md 阶段规划
```

---

## 8. Discord 界面

### 8.1 增强版 Discord Bot 功能

```
# 原版 vs 增强版功能对比

原版:
  ├── Slash Commands: /status, /wake, /stop, /task
  └── 纯文字回复

增强版:
  ├── Slash Commands: 同上
  ├── 自然语言: "status", "wake up", "stop"
  ├── 富文本 Embed: 彩色状态卡片
  ├── 交互按钮: Wake/Stop/Status 快捷操作
  ├── 确认对话框: 危险操作二次确认
  └── 任务线程: 自动创建日志线程
```

### 8.2 新增命令对比

| 原版 | 增强版 | 效果 |
|------|--------|------|
| `/status` | `status` 或 `get status` | 🟢 Embed 状态卡片 |
| `/wake` | `wake` 或 `wake up` | 🟢 启动 + 彩色按钮 |
| `/stop` | `stop` 或 `stop system` | 🔴 确认对话框 |
| `/task ai text` | `ai 你的任务` | 📝 任务 + 线程 |
| `/task code text` | `code 你的任务` | 📝 任务 + 线程 |

### 8.3 切换指南

```bash
# 当前使用原版（默认）
python main.py

# 切换到增强版（需要手动修改代码）
# 1. 备份原版: mv discord_bot.py discord_bot_original.py
# 2. 安装增强版: cp discord_bot_enhanced.py discord_bot.py
# 3. 重启系统: python main.py
```

详见 `DISCORD_FEATURES_COMPARISON.md`

---

## 9. 关键认知

> **AegisOS 不会有"最后一个 Phase"，只有持续治理。**

**Build Phase 交付的是**: 一个能自我演化的系统实体
**Operational Phase 要做的是**: 持续运营这个实体，控制其演化方向

**长期存在的不是代码，而是治理规则。**

---

**版本**: AegisOS v1.0  
**阶段**: Build Phase ✅ Complete / Operational Phase 🚧 Active  
**最后更新**: 2026-02-17
