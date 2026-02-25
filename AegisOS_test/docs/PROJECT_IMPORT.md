# AegisOS 项目导入指南

将未完成的项目导入 AegisOS 进行 AI 辅助开发。

---

## 快速导入

### 1. 使用导入脚本

```powershell
# 导入项目
python import_project.py myproject "C:\path\to\your\project" --desc "项目描述"

# 示例
python import_project.py myapp "C:\Users\me\MyApp" --desc "A web application for task management"
```

### 2. 验证导入

```powershell
# 查看已导入项目
python -c "
import sqlite3
conn = sqlite3.connect('aegisos.db')
cursor = conn.cursor()
cursor.execute('SELECT name, path FROM projects')
for row in cursor.fetchall():
    print(f'{row[0]}: {row[1]}')
conn.close()
"
```

### 3. Discord 中使用

```
# 查看可用项目
/projects

# 对特定项目发起 AI 任务
/task ai: 重构错误处理模块 project=myapp
/task ai: 添加用户认证功能 project=myapp

# 不指定项目（使用 default）
/task ai: 分析代码结构
```

---

## 导入过程说明

### 自动创建的目录结构

```
projects/
└── myproject/                    # 你的项目名称
    ├── agent.md                  # AI 角色配置（自动生成）
    ├── project_desc.md           # 项目描述（自动生成）
    ├── history/                  # 修改历史记录
    │   └── .gitkeep
    └── [你的源代码文件...]        # 从原项目复制
```

### agent.md（AI 角色配置）

导入时自动生成，包含：
- 项目概述
- 技术栈（从代码自动检测）
- 编码规范
- 约束条件

**可手动编辑**以定制 AI 行为。

### project_desc.md（项目描述）

包含：
- 项目摘要
- 目录结构（自动扫描）
- 文件列表
- 导入信息

---

## 项目上下文加载

当对项目发起 AI 任务时，Worker Pool 自动加载：

```python
context = {
    "project_name": "myproject",
    "project_root": "/path/to/projects/myproject",
    "agent_md": "/path/to/projects/myproject/agent.md",
    "agent_content": "...",
    "project_desc": "/path/to/projects/myproject/project_desc.md",
    "project_description": "...",
    "source_files": ["main.py", "utils.py", ...]
}
```

AI 接收的完整 prompt：

```
Project: myproject

Agent Configuration:
[agent.md 内容]

Project Files:
main.py
utils.py
...

Instruction: [你的任务指令]
```

---

## 多项目管理

### 项目切换

```
# 项目 A
/task ai: 修复登录 bug project=projectA

# 项目 B  
/task ai: 优化数据库查询 project=projectB
```

### 默认项目

不指定 `project=` 时使用 `default` 项目。

---

## 导入后操作

### 1. 查看项目文件

```powershell
ls projects/myproject
```

### 2. 编辑 AI 配置

```powershell
notepad projects/myproject/agent.md
```

### 3. 同步源代码变更

如果原项目有更新，重新导入：

```powershell
python import_project.py myproject "C:\path\to\your\project" --desc "Updated"
```

---

## 故障排查

### 项目未显示

```sql
-- 检查数据库
SELECT * FROM projects;

-- 手动添加
INSERT INTO projects (name, path, description) 
VALUES ('myproject', 'C:\AegisOS\projects\myproject', 'Description');
```

### AI 任务未使用项目上下文

检查：
1. 项目目录是否存在
2. agent.md 是否可读
3. Worker Pool 日志中的 context 加载信息

---

## 最佳实践

1. **按功能模块导入**：大型项目分模块导入
2. **定期备份**：`backups/` 目录自动备份
3. **版本标记**：使用 `/evolve` 进行重大变更
4. **Memory 利用**：AI 会自动学习项目模式

---

## 示例：完整导入流程

```powershell
# 1. 准备项目
# 确保源代码在 C:\Projects\WebApp

# 2. 导入
python import_project.py webapp "C:\Projects\WebApp" --desc "Flask web application"

# 3. 验证
/projects
# 输出：📁 Available Projects
#       • webapp

# 4. 发起 AI 任务
/task ai: 分析项目结构并建议改进 project=webapp

# 5. 查看结果（几秒后）
/result [task_id]

# 6. 应用 AI 建议的修改
# AI 返回 JSON Action Schema，包含具体文件修改
```
