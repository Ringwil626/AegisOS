#!/usr/bin/env python3
"""CI Check - Prevent direct runtime table mutations.

This script checks that no module (except runtime_writer) directly
writes to Level 0 tables.
"""
import pathlib
import re
import sys

# Pattern to detect forbidden direct writes
FORBIDDEN = re.compile(
    r'(INSERT INTO tasks|UPDATE tasks|DELETE FROM tasks|'
    r'INSERT INTO usage_ledger|UPDATE usage_ledger|'
    r'INSERT INTO budgets|UPDATE budgets|'
    r'INSERT INTO system_state|UPDATE system_state|'
    r'INSERT INTO heartbeats|UPDATE heartbeats)',
    re.IGNORECASE
)

# Files that are allowed to write (the gateway)
ALLOWED_FILES = {
    'runtime_writer.py',
    'sqlite_store.py',  # Internal implementation
}

def check_file(path: pathlib.Path) -> list:
    """Check a single file for forbidden patterns."""
    violations = []
    
    # Skip allowed files
    if path.name in ALLOWED_FILES:
        return violations
    
    # Skip __pycache__
    if '__pycache__' in str(path):
        return violations
    
    try:
        content = path.read_text(encoding='utf-8')
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            if FORBIDDEN.search(line):
                # Check if it's a comment
                stripped = line.strip()
                if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                
                violations.append({
                    'file': str(path),
                    'line': i,
                    'content': line.strip()[:80]
                })
    except Exception as e:
        print(f"Warning: Could not read {path}: {e}")
    
    return violations


def main():
    """Main check function."""
    print("=" * 70)
    print("RUNTIME WRITE CHECK")
    print("=" * 70)
    print()
    
    all_violations = []
    
    # Check aegisos directory
    for path in pathlib.Path("aegisos").rglob("*.py"):
        violations = check_file(path)
        all_violations.extend(violations)
    
    # Check projects directory (should not write runtime tables)
    if pathlib.Path("projects").exists():
        for path in pathlib.Path("projects").rglob("*.py"):
            violations = check_file(path)
            all_violations.extend(violations)
    
    if all_violations:
        print("[FAIL] FORBIDDEN direct DB writes detected:")
        print()
        for v in all_violations:
            print(f"  File: {v['file']}")
            print(f"  Line {v['line']}: {v['content']}")
            print()
        print("These modules must use runtime_writer API instead.")
        print("Direct mutation of runtime tables is forbidden.")
        print()
        print()
        sys.exit(1)
    else:
        print("[PASS] No forbidden direct writes found.")
        print("[PASS] All runtime table access goes through runtime_writer.")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
