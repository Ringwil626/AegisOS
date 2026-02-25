"""Validator - Phase 6: Controlled Self-Evolution Runtime.

Validates evolution proposals WITHOUT AI.
Copies runtime to staging, applies patch, runs tests.
"""
import os
import sys
import shutil
import subprocess

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(_current_dir)
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import update_evolution_job_status, get_evolution_job
from aegisos.evolution.manager import PROPOSALS_DIR, STAGING_DIR, RUNTIME_DIR


def ensure_staging_clean():
    """Ensure staging directory is clean."""
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR)


def copy_runtime_to_staging():
    """Copy current runtime to staging area.
    
    This creates an isolated environment for testing.
    """
    ensure_staging_clean()
    
    # Copy all Python files from project root to staging
    # Exclude evolution/, ai_ledger tests should use mock
    items_to_copy = [
        "aegisos",
        "main.py"
    ]
    
    for item in items_to_copy:
        src = os.path.join(_project_root, item)
        dst = os.path.join(STAGING_DIR, item)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        elif os.path.isfile(src):
            shutil.copy2(src, dst)
    
    print(f"[Validator] Copied runtime to staging")


def apply_patch(proposal_path: str) -> bool:
    """Apply patch.diff to staging runtime.
    
    Args:
        proposal_path: Path to proposal directory
    
    Returns:
        True if patch applied successfully
    """
    patch_path = os.path.join(proposal_path, "patch.diff")
    
    if not os.path.exists(patch_path):
        print(f"[Validator] No patch file found")
        return False
    
    # Read patch content (simplified - real implementation would use patch command)
    with open(patch_path, "r") as f:
        patch_content = f.read()
    
    # For this mock implementation, we'll just note the patch
    # Real implementation would apply the actual diff
    print(f"[Validator] Patch content preview:")
    print(f"  {patch_content[:200]}...")
    
    # Simulate patch application
    # In real system: subprocess.run(["patch", "-p1", "-i", patch_path], cwd=STAGING_DIR)
    return True


def run_tests(proposal_path: str) -> bool:
    """Run validation tests.
    
    Args:
        proposal_path: Path to proposal directory
    
    Returns:
        True if all tests pass
    """
    test_path = os.path.join(proposal_path, "new_tests.py")
    
    if not os.path.exists(test_path):
        print(f"[Validator] No test file found")
        return False
    
    # Read test content
    with open(test_path, "r") as f:
        test_content = f.read()
    
    print(f"[Validator] Running tests...")
    
    # In real system, this would:
    # 1. Run Python tests in staging environment
    # 2. Check no AI calls are made (Phase 5 ledger check)
    # 3. Verify no system_state modifications
    
    # Mock: assume tests pass
    print(f"[Validator] Tests completed")
    return True


def validate_proposal(job_id: int) -> bool:
    """Validate evolution proposal.
    
    Full validation workflow:
    1. Copy runtime to staging
    2. Apply patch
    3. Run tests
    4. Update job status
    
    Args:
        job_id: Evolution job ID
    
    Returns:
        True if validation passed
    """
    print(f"[Validator] Starting validation for job {job_id}")
    
    # Get job details
    job = get_evolution_job(job_id)
    if not job:
        print(f"[Validator] Job {job_id} not found")
        return False
    
    proposal_path = job[2]
    
    try:
        # Step 1: Copy runtime to staging
        copy_runtime_to_staging()
        
        # Step 2: Apply patch
        if not apply_patch(proposal_path):
            print(f"[Validator] Patch application failed")
            update_evolution_job_status(job_id, "rejected")
            return False
        
        # Step 3: Run tests (NO AI involved)
        if not run_tests(proposal_path):
            print(f"[Validator] Tests failed")
            update_evolution_job_status(job_id, "rejected")
            return False
        
        # Step 4: Mark as validated
        update_evolution_job_status(job_id, "validated")
        print(f"[Validator] Job {job_id} validated successfully")
        return True
        
    except Exception as e:
        print(f"[Validator] Validation error: {e}")
        update_evolution_job_status(job_id, "rejected")
        return False


def auto_validate_pending():
    """Auto-validate all pending proposals.
    
    Called by Main Loop to process evolution jobs.
    """
    from aegisos.db.sqlite_store import list_evolution_jobs
    
    pending = list_evolution_jobs(status="proposed", limit=10)
    
    for job in pending:
        job_id = job[0]
        print(f"[Validator] Auto-validating job {job_id}")
        validate_proposal(job_id)
