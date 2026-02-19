#!/usr/bin/env python3
"""
AegisOS Incremental Governance Checker for PR/Diff
Scans only modified files to validate AI/human contributions
Generates Markdown report for CI/CD integration

Usage:
  python check_governance_pr.py                    # Auto-detect base from env
  python check_governance_pr.py --base=origin/main # Specify base branch
  python check_governance_pr.py --files=file1.py,file2.py  # Direct file list
  python check_governance_pr.py --full             # Full scan fallback
"""

import os
import sys
import ast
import sqlite3
import argparse
from pathlib import Path
from subprocess import check_output, CalledProcessError
from datetime import datetime
from typing import List, Tuple, Optional

ROOT = Path(__file__).resolve().parent

# Approved DB mutation modules (Runtime Contract 1.2)
APPROVED_DB_MODULES = [
    "aegisos.core.executor",
    "aegisos.core.supervisor",
    "aegisos.runtime.manager",
]

# Forbidden imports (Operating Rule 9)
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

# Modules allowed concurrency
ALLOWED_CONCURRENCY_MODULES = [
    "aegisos.core.supervisor",
    "aegisos.core.worker",
    "aegisos.core.message_queue",
]

# Key files to always check
SUPERVISOR_FILE = ROOT / "aegisos" / "core" / "supervisor.py"
EXECUTOR_FILE = ROOT / "aegisos" / "core" / "executor.py"
MANAGER_FILE = ROOT / "aegisos" / "runtime" / "manager.py"

# Critical modules requiring manual review (Runtime Contract core)
CRITICAL_MODULES = [
    SUPERVISOR_FILE,
    EXECUTOR_FILE,
    MANAGER_FILE,
]

# Report path
REPORT_PATH = ROOT / "governance_report_pr.md"


def get_modified_files_from_git(base: str = "origin/main") -> List[Path]:
    """Get modified Python files from git diff."""
    try:
        # Try to get from environment (GitHub Actions, GitLab CI)
        if os.getenv("GITHUB_BASE_REF"):
            base = f"origin/{os.getenv('GITHUB_BASE_REF')}"
        elif os.getenv("CI_MERGE_REQUEST_TARGET_BRANCH_NAME"):
            base = f"origin/{os.getenv('CI_MERGE_REQUEST_TARGET_BRANCH_NAME')}"
        
        result = check_output(
            ["git", "diff", "--name-only", base, "HEAD"],
            cwd=ROOT
        ).decode().strip()
        
        if not result:
            return []
        
        files = []
        for f in result.split("\n"):
            if f.endswith(".py"):
                path = ROOT / f
                if path.exists():
                    files.append(path)
        return files
        
    except CalledProcessError as e:
        print(f"Warning: Failed to get git diff: {e}")
        return []


def get_modified_files_from_env() -> List[Path]:
    """Get modified files from CI environment variables."""
    files = []
    
    # GitHub Actions: changed files
    changed_files = os.getenv("CHANGED_FILES", "")
    if changed_files:
        for f in changed_files.split(","):
            if f.strip().endswith(".py"):
                path = ROOT / f.strip()
                if path.exists():
                    files.append(path)
    
    return files


def get_modified_files(args) -> List[Path]:
    """Get list of modified Python files to check."""
    # Priority 1: Direct file list
    if args.files:
        files = []
        for f in args.files.split(","):
            path = ROOT / f.strip()
            if path.exists() and path.suffix == ".py":
                files.append(path)
        return files
    
    # Priority 2: Environment variables
    env_files = get_modified_files_from_env()
    if env_files:
        return env_files
    
    # Priority 3: Git diff
    git_files = get_modified_files_from_git(args.base)
    if git_files:
        return git_files
    
    # Fallback: empty list (will trigger warning)
    return []


def find_imports(file_path: Path) -> List[str]:
    """Extract imports from Python file."""
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
    return rel_path.as_posix().replace("/", ".").rstrip(".py")


def check_forbidden_imports(files: List[Path]) -> List[str]:
    """Check for forbidden framework imports (Operating Rule 9)."""
    failures = []
    for file in files:
        imports = find_imports(file)
        module_path = get_module_path(file)
        
        for forbidden in FORBIDDEN_IMPORTS:
            if any(i.startswith(forbidden) for i in imports):
                if forbidden in ["asyncio", "threading"]:
                    if any(module_path.startswith(a) for a in ALLOWED_CONCURRENCY_MODULES):
                        continue
                failures.append(
                    f"{file}: forbidden import '{forbidden}' (Operating Rule 9)"
                )
    return failures


def check_supervisor_purity() -> List[str]:
    """Check Supervisor only imports allowed modules (Runtime Contract 1.4)."""
    if not SUPERVISOR_FILE.exists():
        return []
    
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
        return [
            f"{SUPERVISOR_FILE}: forbidden imports {violations} (Runtime Contract 1.4)"
        ]
    return []


def check_critical_module_modifications(files: List[Path]) -> List[str]:
    """
    Check if critical modules are being modified.
    Critical modules require mandatory manual review.
    """
    warnings = []
    for file in files:
        for critical in CRITICAL_MODULES:
            if critical.exists() and file.resolve() == critical.resolve():
                module_name = critical.relative_to(ROOT).as_posix()
                warnings.append(
                    f"{file}: [CRITICAL] {module_name} modified. "
                    f"Manual review REQUIRED before merge."
                )
    return warnings


def check_db_usage(files: List[Path]) -> List[str]:
    """Check DB usage restricted to approved modules (Runtime Contract 1.2)."""
    violations = []
    for file in files:
        if str(file) == str(SUPERVISOR_FILE):
            continue
        
        with file.open("r", encoding="utf-8") as f:
            text = f.read()
        
        if "sqlite_store" not in text:
            continue
        
        module_path = get_module_path(file)
        if any(module_path.startswith(a) for a in APPROVED_DB_MODULES):
            continue
        
        violations.append(
            f"{file}: uses sqlite_store outside approved module (Runtime Contract 1.2)"
        )
    return violations


def check_task_state_management(files: List[Path]) -> List[str]:
    """Check task state transitions only in executor (Runtime Contract 1.3)."""
    violations = []
    for file in files:
        if "executor" in file.as_posix():
            continue
        
        with file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if ".status =" in line or "update_task_status" in line:
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                violations.append(
                    f"{file}:{i}: modifies task status outside executor (Runtime Contract 1.3)"
                )
    return violations


def check_db_integrity(db_path: Path) -> List[str]:
    """Verify DB structure compliance (Runtime Contract 1.5, 1.11)."""
    if not db_path.exists():
        return ["DB not found at aegisos.db"]
    
    failures = []
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Required tables
        required_tables = ["tasks", "system_state", "heartbeats", "audit_log"]
        for table in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                failures.append(f"Table missing: {table}")
        
        # Heartbeats columns
        cursor.execute("PRAGMA table_info(heartbeats)")
        cols = {c[1] for c in cursor.fetchall()}
        required_cols = {"component", "message", "timestamp"}
        
        if not required_cols.issubset(cols):
            missing = required_cols - cols
            failures.append(f"Heartbeats missing columns: {missing}")
        
        # WAL mode
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        if mode != 'wal':
            failures.append(f"WAL mode not enabled (got {mode})")
        
        return failures
    except sqlite3.Error as e:
        return [f"DB error: {e}"]
    finally:
        conn.close()


def generate_report(
    files: List[Path],
    code_errors: List[str],
    db_errors: List[str],
    critical_warnings: List[str] = None
) -> None:
    """Generate Markdown report for PR."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    critical_warnings = critical_warnings or []
    
    # Status: FAIL if errors exist, WARNING if only critical warnings, PASS otherwise
    if code_errors or db_errors:
        status = "FAIL"
    elif critical_warnings:
        status = "WARNING"
    else:
        status = "PASS"
    
    lines = [
        "# AegisOS PR Governance Compliance Report",
        "",
        f"**Generated:** {timestamp}",
        f"**Status:** {status}",
        f"**Files Scanned:** {len(files)}",
        f"**Code Errors:** {len(code_errors)}",
        f"**DB Errors:** {len(db_errors)}",
        f"**Critical Warnings:** {len(critical_warnings)}",
        "",
        "## Modified Files",
        "",
    ]
    
    if files:
        for f in sorted(files):
            lines.append(f"- `{f.relative_to(ROOT)}`")
    else:
        lines.append("- No Python files modified")
    
    lines.extend([
        "",
        "## Summary",
        "",
        f"| Category | Count |",
        f"|----------|-------|",
        f"| Code Compliance | {len(code_errors)} |",
        f"| Database Compliance | {len(db_errors)} |",
        f"| Critical Module Warnings | {len(critical_warnings)} |",
        "",
    ])
    
    # Critical Module Warnings (shown first for visibility)
    if critical_warnings:
        lines.extend([
            "## 🚨 Critical Module Modifications",
            "",
            "The following critical runtime modules have been modified:",
            "",
        ])
        for w in critical_warnings:
            lines.append(f"- {w}")
        lines.extend([
            "",
            "> ⚠️ **Action Required:** These modules control core runtime behavior. "
            "Manual review by a senior maintainer is MANDATORY before merge.",
            "",
        ])
    
    lines.extend([
        "## Code Compliance Failures",
        "",
    ])
    
    if code_errors:
        for e in code_errors:
            lines.append(f"- {e}")
    else:
        lines.append("- None ✅")
    
    lines.extend([
        "",
        "## Database Compliance Failures",
        "",
    ])
    
    if db_errors:
        for e in db_errors:
            lines.append(f"- {e}")
    else:
        lines.append("- None ✅")
    
    lines.extend([
        "",
        "## Governance Reference",
        "",
        "This report validates compliance against:",
        "- [Runtime Contract v1.0](GOVERNANCE.md)",
        "- [Compliance Checklist v1.0](GOVERNANCE.md)",
        "- [AI Developer Operating Rules v1.0](GOVERNANCE.md)",
        "",
        "*Generated by check_governance_pr.py*",
    ])
    
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report generated: {REPORT_PATH}")


def run_checks(files: List[Path]) -> Tuple[List[str], List[str], List[str]]:
    """Run all checks on modified files.
    
    Returns: (code_errors, db_errors, critical_warnings)
    """
    # Always include supervisor check
    check_files = list(files)
    if SUPERVISOR_FILE.exists() and SUPERVISOR_FILE not in check_files:
        check_files.append(SUPERVISOR_FILE)
    
    code_errors = []
    code_errors += check_forbidden_imports(files)
    code_errors += check_supervisor_purity()
    code_errors += check_db_usage(files)
    code_errors += check_task_state_management(files)
    
    # Critical module warnings (require manual review)
    critical_warnings = check_critical_module_modifications(files)
    
    db_errors = check_db_integrity(ROOT / "aegisos.db")
    
    return code_errors, db_errors, critical_warnings


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="AegisOS Incremental Governance Checker for PR"
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base branch for comparison (default: origin/main)"
    )
    parser.add_argument(
        "--files",
        help="Comma-separated list of files to check"
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full scan (all files) instead of incremental"
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip database integrity check"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    print("=" * 70)
    print("AegisOS PR Governance Compliance Checker")
    print("=" * 70)
    print()
    
    args = parse_args()
    
    # Get files to check
    if args.full:
        files = [
            f for f in ROOT.glob("**/*.py")
            if not any(x in str(f) for x in [
                "test_", "backup", "__pycache__", ".venv", "venv",
                "projects/", "projects\\",
            ])
        ]
        print(f"Full scan mode: {len(files)} files")
    else:
        files = get_modified_files(args)
        if not files:
            print("No modified Python files detected in PR.")
            print("Use --full for full scan or --files for specific files.")
            # Don't fail, just nothing to check
            sys.exit(0)
        print(f"Incremental scan: {len(files)} modified files")
    
    print()
    
    # Run checks
    code_errors, db_errors, critical_warnings = run_checks(files)
    
    if args.no_db:
        db_errors = []
        print("Skipping DB checks (--no-db)")
    
    # Generate report
    generate_report(files, code_errors, db_errors, critical_warnings)
    
    # Summary
    print()
    print("=" * 70)
    total_errors = len(code_errors) + len(db_errors)
    
    if total_errors > 0:
        print(f"[FAIL] PR Governance Compliance: {total_errors} violations")
        if critical_warnings:
            print(f"[WARNING] {len(critical_warnings)} critical module(s) modified")
        print("=" * 70)
        sys.exit(1)
    elif critical_warnings:
        # No errors but critical modules modified - exit with warning
        print(f"[WARNING] PR Governance Compliance: {len(critical_warnings)} critical module(s) modified")
        print("Manual review required before merge.")
        print("=" * 70)
        sys.exit(2)  # Special exit code for warning-only
    else:
        print("[PASS] PR Governance Compliance")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
