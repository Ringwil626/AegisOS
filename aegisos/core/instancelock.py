"""Instance Lock - P0-1 Production Hardening.

Prevents multiple runtime instances from running simultaneously.
Uses standard library only (no psutil dependency).
"""
import os
import sys

LOCK_FILE = "aegisos.lock"


def _pid_exists(pid: int) -> bool:
    """Check if a process with given PID exists.
    
    Uses standard library only (Windows compatible).
    """
    if sys.platform == 'win32':
        # Windows: use ctypes to check process
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(1, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        # Unix: check /proc
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def acquire_lock() -> tuple[bool, str]:
    """Acquire instance lock.
    
    Returns:
        (success, mode) where mode is 'clean' or 'recovered'
    """
    if os.path.exists(LOCK_FILE):
        # Check if PID is still alive
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            if _pid_exists(old_pid):
                print(f"[InstanceLock] Another instance is running (PID: {old_pid})")
                return False, "blocked"
            else:
                print(f"[InstanceLock] Found stale lock from crashed process {old_pid}")
                # Crash recovery mode
                _write_lock()
                return True, "recovered"
        except (ValueError, IOError) as e:
            print(f"[InstanceLock] Corrupted lock file: {e}")
            _write_lock()
            return True, "recovered"
    else:
        # Clean start
        _write_lock()
        return True, "clean"


def _write_lock():
    """Write current PID to lock file."""
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))


def release_lock():
    """Release instance lock (graceful shutdown)."""
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
            print("[InstanceLock] Lock released")
        except OSError as e:
            print(f"[InstanceLock] Error releasing lock: {e}")


def is_locked() -> bool:
    """Check if another instance holds the lock."""
    if not os.path.exists(LOCK_FILE):
        return False
    
    try:
        with open(LOCK_FILE, 'r') as f:
            pid = int(f.read().strip())
        return _pid_exists(pid)
    except (ValueError, IOError):
        return False
