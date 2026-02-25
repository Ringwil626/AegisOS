#!/usr/bin/env python3
"""
AegisOS Governance Compliance Checker with Report
Checks codebase for:
- Runtime Contract adherence
- Compliance Checklist rules
- AI Developer Operating Rules

Generates Markdown report with detailed failures for CI/CD integration.

Exit codes:
  0 - All checks passed (compliant)
  1 - One or more checks failed (non-compliant)

Usage:
  python check_governance.py              # Static + DB checks, generate report
  python check_governance.py --no-db      # Static checks only
  python check_governance.py --csv        # Generate CSV report instead of Markdown
"""

import os
import sys
import ast
import sqlite3
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Root directory of repository
ROOT = Path(__file__).resolve().parent

# Files to scan for static checks (exclude tests, backups, projects, self)
CODE_FILES = [
    f for f in ROOT.glob("**/*.py")
    if not any(x in str(f) for x in [
        "test_", "backup", "__pycache__", ".venv", "venv",
        "projects/", "projects\\",
        "import_project.py",
        "check_governance.py"
    ])
]

# Approved DB mutation modules (from Runtime Contract 1.2)
APPROVED_DB_MODULES = [
    "aegisos.core.executor",
    "aegisos.core.supervisor",
    "aegisos.runtime.manager",
]

# Forbidden imports for AI influence / agent frameworks (Operating Rule 9)
FORBIDDEN_IMPORTS = [
    "celery",
    "langchain",
    "langgraph",
    "crewai",
    "autogen",
    "eventbus",
    "event_bus",
    "dependency_injector",
    "injector",
    "asyncio",
    "aiohttp",
]

# Modules allowed to use threading/asyncio
ALLOWED_CONCURRENCY_MODULES = [
    "aegisos.core.supervisor",
    "aegisos.core.worker",
    "aegisos.core.message_queue",
]

# Key file paths
SUPERVISOR_FILE = ROOT / "aegisos" / "core" / "supervisor.py"
WORKER_FILE = ROOT / "aegisos" / "core" / "worker.py"
EXECUTOR_FILE = ROOT / "aegisos" / "core" / "executor.py"

# Report output paths
REPORT_MD = ROOT / "governance_report.md"
REPORT_CSV = ROOT / "governance_report.csv"


def find_imports(file_path: Path) -> List[str]:
    """Return list of module names imported in the file."""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
        node = ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}")
        return []
    
    imports = []
    for n in ast.walk(node):
        if isinstance(n, ast.Import):
            for alias in n.names:
                imports.append(alias.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                imports.append(n.module)
    return imports


def get_module_path(file_path: Path) -> str:
    """Convert file path to Python module path."""
    rel_path = file_path.relative_to(ROOT)
    module = rel_path.as_posix().replace("/", ".").rstrip(".py")
    return module


def check_forbidden_imports() -> List[str]:
    """Check 1: Forbidden framework imports (Operating Rule 9)."""
    failures = []
    for file in CODE_FILES:
        imports = find_imports(file)
        module_path = get_module_path(file)
        
        for forbidden in FORBIDDEN_IMPORTS:
            if any(i.startswith(forbidden) for i in imports):
                if forbidden in ["asyncio", "threading"]:
                    if any(module_path.startswith(a) for a in ALLOWED_CONCURRENCY_MODULES):
                        continue
                failures.append(f"{file}: forbidden import '{forbidden}' (Operating Rule 9)")
    return failures


def check_supervisor_purity() -> List[str]:
    """Check 2: Supervisor must be 'dumb' (Runtime Contract 1.4)."""
    if not SUPERVISOR_FILE.exists():
        return [f"Supervisor file not found: {SUPERVISOR_FILE}"]
    
    allowed = {
        "aegisos.db.sqlite_store",
        "threading",
        "time",
        "os",
        "sys",
    }
    
    imports = set(find_imports(SUPERVISOR_FILE))
    violations = imports - allowed
    
    if violations:
        return [f"{SUPERVISOR_FILE}: forbidden imports {violations} (Runtime Contract 1.4)"]
    return []


def check_db_usage_restrictions() -> List[str]:
    """Check 3: DB access restricted to approved modules (Runtime Contract 1.2)."""
    violations = []
    
    # Files exempt from DB usage check (DB layer itself and tools)
    EXEMPT_FILES = [
        "sqlite_store.py",           # DB layer definition
        "check_governance_pr.py",    # Governance tool
    ]
    
    for file in CODE_FILES:
        with file.open("r", encoding="utf-8") as f:
            text = f.read()
        
        if "sqlite_store" not in text:
            continue
        
        # Skip exempt files
        if any(exempt in file.name for exempt in EXEMPT_FILES):
            continue
        
        module_path = get_module_path(file)
        if any(module_path.startswith(a) for a in APPROVED_DB_MODULES):
            continue
        
        if "test" in module_path:
            continue
        
        violations.append(
            f"{file}: uses sqlite_store outside approved module (Runtime Contract 1.2)"
        )
    return violations


def check_task_state_management() -> List[str]:
    """Check 4: Task state transitions only in executor (Runtime Contract 1.3)."""
    violations = []
    
    # Files exempt from this check (tools and DB layer itself)
    EXEMPT_FILES = [
        "check_governance_pr.py",
        "sqlite_store.py",
    ]
    
    for file in CODE_FILES:
        # Skip executor files
        if "executor" in file.as_posix():
            continue
        
        # Skip exempt files
        if any(exempt in file.name for exempt in EXEMPT_FILES):
            continue
        
        with file.open("r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split('\n')
        
        in_docstring = False
        docstring_delim = None
        
        for i, line in enumerate(lines, 1):
            # Track docstrings
            if '"""' in line or "'''" in line:
                # Count occurrences to handle single-line docstrings
                double_quotes = line.count('"""')
                single_quotes = line.count("'''")
                
                if not in_docstring:
                    # Entering docstring
                    if double_quotes >= 2 or single_quotes >= 2:
                        # Single-line docstring, skip this line
                        continue
                    elif double_quotes > 0:
                        in_docstring = True
                        docstring_delim = '"""'
                        continue
                    elif single_quotes > 0:
                        in_docstring = True
                        docstring_delim = "'''"
                        continue
                else:
                    # Exiting docstring
                    if docstring_delim in line:
                        in_docstring = False
                        docstring_delim = None
                        continue
            
            if in_docstring:
                continue
            
            # Check for direct status assignment
            if ".status =" in line:
                stripped = line.strip()
                
                # Skip comments
                if stripped.startswith('#'):
                    continue
                
                violations.append(
                    f"{file}:{i}: modifies task status outside executor (Runtime Contract 1.3)"
                )
            
            # Check for update_task_status FUNCTION CALLS (not imports/definitions)
            if "update_task_status(" in line:
                stripped = line.strip()
                
                # Skip comments
                if stripped.startswith('#'):
                    continue
                
                # Skip function definition itself
                if "def update_task_status" in line:
                    continue
                
                violations.append(
                    f"{file}:{i}: modifies task status outside executor (Runtime Contract 1.3)"
                )
    return violations


def check_db_integrity(db_path: Path) -> List[str]:
    """Check 5: DB structure compliance (Runtime Contract 1.5, 1.11)."""
    if not db_path.exists():
        return ["DB not found at aegisos.db"]
    
    failures = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check required tables
        required_tables = ["tasks", "system_state", "heartbeats", "audit_log"]
        for table in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                failures.append(f"Table missing: {table}")
        
        # Check heartbeats structure
        cursor.execute("PRAGMA table_info(heartbeats)")
        cols = {c[1] for c in cursor.fetchall()}
        required_cols = {"component", "message", "timestamp"}
        
        if not required_cols.issubset(cols):
            missing = required_cols - cols
            failures.append(f"Heartbeats table missing columns: {missing}")
        
        # Check WAL mode
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        if mode != 'wal':
            failures.append(f"WAL mode not enabled (got {mode})")
        
        return failures
    except sqlite3.Error as e:
        return [f"DB error: {e}"]
    finally:
        conn.close()


def run_all_checks() -> Tuple[List[str], List[str]]:
    """Run all checks and return (code_errors, db_errors)."""
    code_errors = []
    
    checks = [
        check_forbidden_imports,
        check_supervisor_purity,
        check_db_usage_restrictions,
        check_task_state_management,
    ]
    
    for check_func in checks:
        code_errors.extend(check_func())
    
    db_errors = check_db_integrity(ROOT / "aegisos.db")
    
    return code_errors, db_errors


def generate_markdown_report(code_errors: List[str], db_errors: List[str]) -> None:
    """Generate Markdown report for CI/CD display."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_errors = len(code_errors) + len(db_errors)
    status = "PASS" if total_errors == 0 else "FAIL"
    
    lines = [
        "# AegisOS Governance Compliance Report",
        "",
        f"**Generated:** {timestamp}",
        f"**Status:** {'✅ PASS' if status == 'PASS' else '❌ FAIL'}",
        f"**Total Errors:** {total_errors}",
        "",
        "## Summary",
        "",
        f"| Category | Errors |",
        f"|----------|--------|",
        f"| Code Compliance | {len(code_errors)} |",
        f"| Database Compliance | {len(db_errors)} |",
        "",
        "## Code Compliance Failures",
        "",
    ]
    
    if code_errors:
        for e in code_errors:
            lines.append(f"- {e}")
    else:
        lines.append("- None")
    
    lines.extend([
        "",
        "## Database Compliance Failures",
        "",
    ])
    
    if db_errors:
        for e in db_errors:
            lines.append(f"- {e}")
    else:
        lines.append("- None")
    
    lines.extend([
        "",
        "## Governance Reference",
        "",
        "This report checks compliance against:",
        "- Runtime Contract v1.0",
        "- Compliance Checklist v1.0",
        "- AI Developer Operating Rules v1.0",
        "",
        "*Generated automatically by check_governance.py*",
    ])
    
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Markdown report generated: {REPORT_MD}")


def generate_csv_report(code_errors: List[str], db_errors: List[str]) -> None:
    """Generate CSV report for spreadsheet import."""
    timestamp = datetime.now().isoformat()
    
    rows = []
    for error in code_errors:
        rows.append({
            "timestamp": timestamp,
            "category": "Code",
            "severity": "ERROR",
            "message": error,
        })
    for error in db_errors:
        rows.append({
            "timestamp": timestamp,
            "category": "Database",
            "severity": "ERROR",
            "message": error,
        })
    
    if not rows:
        rows.append({
            "timestamp": timestamp,
            "category": "General",
            "severity": "INFO",
            "message": "All governance checks passed",
        })
    
    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "category", "severity", "message"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"CSV report generated: {REPORT_CSV}")


def main():
    """Main entry point."""
    print("=" * 70)
    print("AegisOS Governance Compliance Checker")
    print("Checking against: Runtime Contract + Compliance Checklist + Operating Rules")
    print("=" * 70)
    print()
    
    # Parse arguments
    use_db = "--no-db" not in sys.argv
    csv_format = "--csv" in sys.argv
    
    # Run checks
    code_errors, db_errors = run_all_checks()
    
    if not use_db:
        db_errors = []
        print("Skipping DB checks (--no-db)")
    
    # Generate report
    if csv_format:
        generate_csv_report(code_errors, db_errors)
    else:
        generate_markdown_report(code_errors, db_errors)
    
    # Summary output
    print()
    print("=" * 70)
    total = len(code_errors) + len(db_errors)
    
    if total > 0:
        print(f"Governance Compliance FAIL: {total} violations found")
        print("=" * 70)
        sys.exit(1)
    else:
        print("Governance Compliance PASS")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
