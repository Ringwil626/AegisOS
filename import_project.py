#!/usr/bin/env python3
"""AegisOS Project Importer - 导入未完成项目"""
import os
import sys
import shutil
import sqlite3
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from aegisos.db.sqlite_store import DB_PATH


def import_project(project_name: str, source_path: str, description: str = ""):
    """
    导入未完成项目到 AegisOS
    
    Args:
        project_name: 项目名称 (英文，无空格)
        source_path: 源代码目录路径
        description: 项目描述
    """
    # 1. 创建项目目录结构
    project_root = Path(f"projects/{project_name}")
    project_root.mkdir(parents=True, exist_ok=True)
    
    # 2. 复制源代码
    source = Path(source_path)
    if not source.exists():
        print(f"[ERROR] Source directory not found: {source_path}")
        return False
    
    # 复制所有文件到项目目录
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, project_root / item.name)
        elif item.is_dir() and item.name not in ['.git', '__pycache__', 'node_modules']:
            shutil.copytree(item, project_root / item.name, dirs_exist_ok=True)
    
    print(f"[OK] Copied {len(list(source.rglob('*')))} files")
    
    # 3. 创建 agent.md (项目角色/指令)
    agent_md = project_root / "agent.md"
    agent_content = f"""# {project_name} - AI Assistant Configuration

## Project Overview
{description or f"Project: {project_name}"}

## Technology Stack
- Language: Detect from source files
- Framework: Auto-detect

## Coding Standards
- Follow existing code style
- Maintain consistency with existing patterns
- Add comments for complex logic

## Constraints
- Do not break existing functionality
- Maintain backward compatibility
- Test changes before committing

## History
Imported on: Auto-generated
"""
    agent_md.write_text(agent_content, encoding='utf-8')
    print(f"[OK] Created agent.md")
    
    # 4. 创建 project_desc.md
    desc_md = project_root / "project_desc.md"
    
    # 自动分析项目结构
    file_list = []
    for f in sorted(project_root.rglob('*')):
        if f.is_file() and f.name not in ['agent.md', 'project_desc.md']:
            rel_path = f.relative_to(project_root)
            file_list.append(f"  - {rel_path}")
    
    desc_content = f"""# {project_name} - Project Description

## Summary
{description}

## Directory Structure
```
{project_name}/
"""
    # 添加文件树
    for f in file_list[:30]:  # 限制前30个文件
        desc_content += f + "\n"
    if len(file_list) > 30:
        desc_content += f"  ... and {len(file_list) - 30} more files\n"
    
    desc_content += f"""```

## Import Information
- Source: {source_path}
- Imported: {__import__('datetime').datetime.now().isoformat()}
- Total Files: {len(file_list)}

## Next Steps
1. Review agent.md and customize AI behavior
2. Use `/task` to request modifications
3. Use `/evolve` for major refactoring
"""
    desc_md.write_text(desc_content, encoding='utf-8')
    print(f"[OK] Created project_desc.md")
    
    # 5. 创建 history 目录
    history_dir = project_root / "history"
    history_dir.mkdir(exist_ok=True)
    (history_dir / ".gitkeep").write_text("")
    print(f"[OK] Created history/ directory")
    
    # 6. 注册到数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建项目表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            path TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at REAL DEFAULT (unixepoch()),
            updated_at REAL DEFAULT (unixepoch())
        )
    ''')
    
    # 插入项目记录
    cursor.execute(
        "INSERT OR REPLACE INTO projects (name, path, description, status) VALUES (?, ?, ?, ?)",
        (project_name, str(project_root.absolute()), description, "active")
    )
    
    conn.commit()
    conn.close()
    print(f"[OK] Project registered in database")
    
    # 7. 创建初始工程记忆（写入 engineering_memory 表）
    try:
        from aegisos.db.sqlite_store import create_memory_record
        create_memory_record(
            problem_summary=f"Project {project_name} imported",
            solution_summary=f"Imported from {source_path}. {description}",
            tags=f"import,{project_name}",
            outcome="success"
        )
        print(f"[OK] Created initial engineering memory")
    except Exception as e:
        print(f"[WARN] Could not create memory: {e}")
    
    print(f"\n[SUCCESS] Project '{project_name}' imported successfully!")
    print(f"   位置: {project_root.absolute()}")
    print(f"   使用: /task ai: 修改 {project_name} 的...")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import project into AegisOS")
    parser.add_argument("name", help="Project name (no spaces)")
    parser.add_argument("source", help="Source directory path")
    parser.add_argument("--desc", "-d", default="", help="Project description")
    
    args = parser.parse_args()
    
    import_project(args.name, args.source, args.desc)
