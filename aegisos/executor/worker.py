"""Worker Pool - Phase 5C: Async AI Execution with Budget Guard.

Architecture:
    Main Loop (Gate + Budget Pre-check) → Worker Pool (AI Execution) → Callback (Ledger + DB)

Design Principles:
    - Gate control stays in Main Loop (Phase 4)
    - Budget pre-check before submission (Phase 5)
    - Actual Ledger write after execution (Phase 5)
    - Supports timeout and cancellation
    - Thread-safe database access
"""
import os
import sys
import time
import sqlite3
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, Future, TimeoutError as FutureTimeoutError
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.ai.executor import execute_with_budget_guard, mock_ai_call
from aegisos.db.sqlite_store import (
    update_task_status,
    append_task_result,
    write_heartbeat,
    DB_PATH
)


# Global AI call function (can be injected by main.py for Kimi API)
_kimi_call: Optional[Callable[[str], tuple[str, int, int]]] = None

def set_ai_call_function(func: Callable[[str], tuple[str, int, int]]):
    """Set the AI call function (used by main.py to inject Kimi client)."""
    global _kimi_call
    _kimi_call = func


class TaskState(Enum):
    """Worker task states."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class WorkerTask:
    """Task metadata for worker execution."""
    task_id: int
    task_type: str
    payload: str
    model: str = "kimi"
    timeout: int = 300  # 5 minutes default
    submitted_at: float = 0
    started_at: float = 0
    completed_at: float = 0
    future: Optional[Future] = None
    result: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0
    cost: float = 0.0


class WorkerPool:
    """Managed thread pool for AI task execution.
    
    Ensures:
    - Main Loop keeps control (Gate + Budget pre-check)
    - Non-blocking execution
    - Proper Ledger accounting
    - Timeout and cancellation support
    """
    
    _instance: Optional["WorkerPool"] = None
    _lock = threading.Lock()
    
    def __new__(cls, max_workers: int = 3):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_workers: int = 3):
        if self._initialized:
            return
        
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_tasks: Dict[int, WorkerTask] = {}
        self._completed_tasks: Dict[int, WorkerTask] = {}
        self._lock = threading.Lock()
        self._db_lock = threading.Lock()  # SQLite thread safety
        self._initialized = True
        
        print(f"[WorkerPool] Initialized with {max_workers} workers")
    
    def start(self):
        """Start the worker pool."""
        if self._executor is None or self._executor._shutdown:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="aegisos_worker"
            )
            print(f"[WorkerPool] Started with {self.max_workers} workers")
    
    def stop(self, wait: bool = True, timeout: float = 30):
        """Stop the worker pool gracefully."""
        with self._lock:
            # Cancel pending tasks
            for task_id, task in list(self._active_tasks.items()):
                if task.future and not task.future.done():
                    task.future.cancel()
                    task.error = "Worker pool shutdown"
                    self._update_task_in_db(task_id, "cancelled", "Worker pool shutdown")
            
            if self._executor:
                self._executor.shutdown(wait=wait, cancel_futures=True)
                self._executor = None
        
        print("[WorkerPool] Stopped")
    
    def submit(self, task_id: int, task_type: str, payload: str, 
               model: str = "kimi", timeout: int = 300) -> bool:
        """Submit task to worker pool.
        
        Args:
            task_id: Task ID from database
            task_type: Task type ("ai", "command", etc.)
            payload: Task payload
            model: AI model to use
            timeout: Execution timeout in seconds
        
        Returns:
            True if submitted successfully
        
        Note:
            Budget pre-check should be done by Main Loop before submission.
            This method assumes budget is already validated.
        """
        if not self._executor:
            print("[WorkerPool] Error: Pool not started")
            return False
        
        with self._lock:
            if task_id in self._active_tasks:
                print(f"[WorkerPool] Task {task_id} already active")
                return False
            
            # Create task metadata
            task = WorkerTask(
                task_id=task_id,
                task_type=task_type,
                payload=payload,
                model=model,
                timeout=timeout,
                submitted_at=time.time()
            )
            
            # Submit to thread pool
            future = self._executor.submit(self._execute_task_wrapper, task)
            task.future = future
            self._active_tasks[task_id] = task
            
            print(f"[WorkerPool] Task {task_id} submitted (timeout: {timeout}s)")
            return True
    
    def _execute_task_wrapper(self, task: WorkerTask) -> None:
        """Wrapper for task execution with state tracking."""
        task.started_at = time.time()
        
        try:
            # Update DB to running via runtime_writer (enforced by firewall)
            try:
                from aegisos.db.runtime_writer import update_task_status
                update_task_status(task.task_id, "running")
            except Exception as db_err:
                print(f"[WorkerPool] DB update error (running): {db_err}")
            
            # Execute based on task type
            if task.task_type in ("ai", "code") or task.payload.lower().startswith(("ai:", "ai ", "ai：", "kimi:", "kimi ", "kimi：")):
                result = self._execute_ai_task(task, task_type=task.task_type)
            elif task.task_type == "command":
                result = self._execute_command_task(task)
            else:
                result = self._execute_mock_task(task)
            
            task.result = result
            task.completed_at = time.time()
            
            # Update DB to completed
            try:
                # Use runtime_writer for Level 0 table writes
                from aegisos.db.runtime_writer import update_task_status, update_task_payload
                new_payload = task.payload + "\nRESULT: " + result
                update_task_payload(task.task_id, new_payload)
                update_task_status(task.task_id, "completed")
            except Exception as db_err:
                print(f"[WorkerPool] DB update error (completed): {db_err}")
            
            print(f"[WorkerPool] Task {task.task_id} completed")
            
            # Push notification to Discord via message queue
            try:
                from aegisos.core.message_queue import push_task_notification
                
                # Get channel ID from config (simple parsing)
                channel_id = None
                try:
                    with open('config.yaml', 'r', encoding='utf-8') as f:
                        for line in f:
                            if 'task_status:' in line:
                                parts = line.split(':')[1].strip().split()
                                channel_id = parts[0].strip('"\'') if parts else None
                                break
                except:
                    pass
                
                # Get task info
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT project, payload FROM tasks WHERE id = ?", (task.task_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row and channel_id:
                    project = row[0] or "default"
                    task_name = row[1].split('\n')[0][:100]
                    result_summary = result[:300] if len(result) > 300 else result
                    
                    push_task_notification(
                        task_id=task.task_id,
                        task_name=task_name,
                        project=project,
                        status="completed",
                        result_summary=result_summary,
                        channel_id=channel_id
                    )
                    print(f"[WorkerPool] Push notification queued for task {task.task_id}")
            except Exception as push_err:
                print(f"[WorkerPool] Push queue error: {push_err}")
            
        except FutureTimeoutError:
            task.error = f"Timeout after {task.timeout}s"
            task.completed_at = time.time()
            
            try:
                # Use runtime_writer for Level 0 table writes
                from aegisos.db.runtime_writer import update_task_status, update_task_payload
                update_task_payload(task.task_id, task.payload + "\nRESULT: TIMEOUT")
                update_task_status(task.task_id, "failed")
            except Exception as db_err:
                print(f"[WorkerPool] DB update error (timeout): {db_err}")
            
            print(f"[WorkerPool] Task {task.task_id} timeout")
            
            # Push timeout notification
            try:
                from aegisos.core.message_queue import push_task_notification
                
                channel_id = None
                try:
                    with open('config.yaml', 'r', encoding='utf-8') as f:
                        for line in f:
                            if 'task_status:' in line:
                                parts = line.split(':')[1].strip().split()
                                channel_id = parts[0].strip('"\'') if parts else None
                                break
                except:
                    pass
                
                if channel_id:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("SELECT project, payload FROM tasks WHERE id = ?", (task.task_id,))
                    row = conn.fetchone()
                    conn.close()
                    
                    if row:
                        push_task_notification(
                            task_id=task.task_id,
                            task_name=row[1].split('\n')[0][:100],
                            project=row[0] or "default",
                            status="failed",
                            result_summary=f"Timeout after {task.timeout}s",
                            channel_id=channel_id
                        )
            except:
                pass
            
        except Exception as e:
            task.error = str(e)
            task.completed_at = time.time()
            
            try:
                # Use runtime_writer for Level 0 table writes
                from aegisos.db.runtime_writer import update_task_status, update_task_payload
                update_task_payload(task.task_id, task.payload + f"\nRESULT: ERROR: {e}")
                update_task_status(task.task_id, "failed")
            except Exception as db_err:
                print(f"[WorkerPool] DB update error (failed): {db_err}")
            
            print(f"[WorkerPool] Task {task.task_id} failed: {e}")
        
        finally:
            # Move to completed dict
            with self._lock:
                if task.task_id in self._active_tasks:
                    self._completed_tasks[task.task_id] = task
                    del self._active_tasks[task.task_id]
    
    def _load_project_context(self, task: WorkerTask) -> dict:
        """Load project context for AI task with key file contents."""
        context = {}
        
        # Get project from task (stored in DB)
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT project FROM tasks WHERE id = ?", (task.task_id,))
            row = cursor.fetchone()
            project_name = row[0] if row and row[0] else "default"
            conn.close()
        except:
            project_name = "default"
        
        # Build project paths
        project_root = Path(f"projects/{project_name}")
        if project_root.exists():
            context["project_name"] = project_name
            context["project_root"] = str(project_root.absolute())
            
            # Load agent.md if exists (limited to 500 chars)
            agent_md = project_root / "agent.md"
            if agent_md.exists():
                context["agent_md"] = str(agent_md.absolute())
                context["agent_content"] = agent_md.read_text(encoding='utf-8')[:500]
            
            # Load project_desc.md if exists (limited to 500 chars)
            desc_md = project_root / "project_desc.md"
            if desc_md.exists():
                context["project_desc"] = str(desc_md.absolute())
                context["project_description"] = desc_md.read_text(encoding='utf-8')[:500]
            
            # Load key documentation files automatically (very limited size)
            key_files = {
                "readme": ["README.md", "readme.md"],
            }
            
            for key, filenames in key_files.items():
                for filename in filenames:
                    file_path = project_root / filename
                    if file_path.exists():
                        try:
                            content = file_path.read_text(encoding='utf-8')
                            # Very limited to avoid token overflow
                            context[f"{key}_content"] = content[:800] + "..." if len(content) > 800 else content
                            break
                        except Exception as e:
                            context[f"{key}_error"] = str(e)
            
            # Load only 1-2 main Python files with very limited content
            main_scripts = []
            src_dir = project_root / "src"
            if src_dir.exists():
                py_files = list(src_dir.glob("*.py"))[:2]  # Only first 2
            else:
                py_files = list(project_root.glob("*.py"))[:2]
            
            for py_file in py_files:
                try:
                    content = py_file.read_text(encoding='utf-8')
                    main_scripts.append({
                        "file": str(py_file.relative_to(project_root)),
                        "content": content[:500] + "..." if len(content) > 500 else content
                    })
                except:
                    pass
            context["main_scripts"] = main_scripts
            
            # List source files (for context)
            source_files = []
            for f in project_root.rglob("*"):
                if f.is_file() and f.name not in ['agent.md', 'project_desc.md', '.gitkeep']:
                    rel_path = f.relative_to(project_root)
                    source_files.append(str(rel_path))
                    if len(source_files) >= 30:  # Limit to 30 files
                        break
            context["source_files"] = source_files
            context["file_count"] = len(source_files)
        
        return context
    
    def _execute_ai_task(self, task: WorkerTask, task_type: str = "ai") -> str:
        """Execute AI task with budget guard and project context.
        
        Args:
            task: WorkerTask instance
            task_type: "ai" for general AI, "code" for coding-optimized
        """
        # Remove prefixes if present
        prompt = task.payload
        for prefix in ["ai:", "ai ", "ai：", "kimi:", "kimi ", "kimi：", "code:", "code ", "code："]:
            if prompt.lower().startswith(prefix):
                prompt = prompt[len(prefix):].strip()
                break
        
        # Load project context with file contents
        context = self._load_project_context(task)
        
        # Determine temperature and system prompt based on task type
        if task_type == "code":
            temperature = 0.1  # Low temperature for deterministic code
            system_msg = "You are a coding assistant. Generate high-quality code with proper error handling."
        else:
            temperature = 1.0  # Higher temperature for creative/general tasks
            system_msg = "You are a helpful AI assistant."
        
        # Build prompt with loaded content (limited size)
        if context:
            context_parts = [f"Project: {context.get('project_name', 'default')}"]
            
            # Add brief README summary if available
            if "readme_content" in context:
                context_parts.append(f"\nREADME Summary:\n{context['readme_content'][:300]}")
            
            # Add file list (brief)
            if context.get("source_files"):
                files = context["source_files"][:10]
                context_parts.append(f"\nKey Files: {', '.join(files)}")
            
            # Add brief code samples (more for code tasks)
            if context.get("main_scripts"):
                if task_type == "code":
                    # Include more code context for code tasks
                    for script in context["main_scripts"][:2]:
                        context_parts.append(f"\nCode ({script['file']}):\n{script['content'][:500]}")
                else:
                    script = context["main_scripts"][0]
                    context_parts.append(f"\nSample Code ({script['file']}):\n{script['content'][:300]}")
            
            # Add the actual instruction
            context_parts.append(f"\n\nTASK: {prompt}")
            
            if task_type == "code":
                context_parts.append("\nProvide specific, actionable code changes. Include error handling and follow best practices.")
            else:
                context_parts.append("\nProvide a clear, concise answer based on the project information above.")
            
            full_prompt = chr(10).join(context_parts)
        else:
            full_prompt = prompt
        
        # Try to use KimiClient directly for temperature control
        try:
            # Use inference executor for AI calls
            from aegisos.executor.inference_executor import ContractInferenceExecutor
            executor = ContractInferenceExecutor(project=context.get('project', 'default'))
            
            # Call with contract-based execution
            from aegisos.core.state_builder import ActionType
            inference_result = executor.execute_contract(
                task_id=str(task.task_id),
                action=ActionType.ANALYZE_CODE,
                inputs={'prompt': full_prompt, 'context': context}
            )
            result = inference_result.output_text if inference_result.success else {}
            response_json = json.dumps(result)
            
            # Log usage to ledger
            prompt_tokens = len(full_prompt) // 4
            completion_tokens = len(response_json) // 4
            from aegisos.db.ledger import log_ai_usage
            log_ai_usage(task.task_id, task.model, prompt_tokens, completion_tokens, status="committed")
            
            return response_json
            
        except Exception as e:
            # Fallback to standard AI call function
            print(f"[WorkerPool] Direct KimiClient call failed: {e}, using fallback")
            ai_call_func = _kimi_call if _kimi_call is not None else mock_ai_call
            
            success, response = execute_with_budget_guard(
                task_id=task.task_id,
                model=task.model,
                prompt=full_prompt,
                ai_call_func=ai_call_func
            )
            
            if not success:
                raise RuntimeError(f"AI execution failed: {response}")
            
            return response
    
    def _execute_command_task(self, task: WorkerTask) -> str:
        """Execute shell command task directly.
        
        P7 Security: Commands are executed directly without AI.
        """
        import subprocess
        
        command = task.payload.strip()
        
        # Remove 'command:' prefix if present
        if command.lower().startswith(("command:", "cmd:")):
            command = command.split(":", 1)[1].strip()
        
        # Get project path for execution context
        project_path = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT project FROM tasks WHERE id = ?", (task.task_id,))
            row = cursor.fetchone()
            if row and row[0] and row[0] != "default":
                project_path = f"projects/{row[0]}"
            conn.close()
        except:
            pass
        
        # Execute command with timeout
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=task.timeout
            )
            
            output = []
            if result.stdout:
                output.append(f"STDOUT:\n{result.stdout[:2000]}")
            if result.stderr:
                output.append(f"STDERR:\n{result.stderr[:1000]}")
            
            exit_msg = f"Exit code: {result.returncode}"
            output.append(exit_msg)
            
            return chr(10).join(output)
            
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {task.timeout}s"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    def _execute_mock_task(self, task: WorkerTask) -> str:
        """Execute mock task (deterministic)."""
        import time
        time.sleep(2)
        return f"Executed: {task.payload}"
    
    def _update_task_in_db(self, task_id: int, status: str, result: str):
        """Thread-safe DB update."""
        with self._db_lock:
            try:
                update_task_status(task_id, status)
                append_task_result(task_id, result)
            except Exception as e:
                print(f"[WorkerPool] DB update error: {e}")
    
    def get_active_count(self) -> int:
        """Get number of active tasks."""
        with self._lock:
            return len(self._active_tasks)
    
    def get_active_tasks(self) -> Dict[int, WorkerTask]:
        """Get copy of active tasks."""
        with self._lock:
            return dict(self._active_tasks)
    
    def is_task_complete(self, task_id: int) -> bool:
        """Check if task is completed."""
        with self._lock:
            return task_id in self._completed_tasks
    
    def get_task_result(self, task_id: int) -> Optional[WorkerTask]:
        """Get completed task result."""
        with self._lock:
            return self._completed_tasks.get(task_id)
    
    def clean_completed(self, max_age: float = 3600):
        """Clean old completed tasks."""
        now = time.time()
        with self._lock:
            to_remove = [
                tid for tid, task in self._completed_tasks.items()
                if now - task.completed_at > max_age
            ]
            for tid in to_remove:
                del self._completed_tasks[tid]


# Module-level singleton
_worker_pool: Optional[WorkerPool] = None


def get_worker_pool(max_workers: int = 3) -> WorkerPool:
    """Get or create WorkerPool singleton."""
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = WorkerPool(max_workers=max_workers)
    return _worker_pool


def init_worker_pool(max_workers: int = 3) -> WorkerPool:
    """Initialize and start worker pool."""
    pool = get_worker_pool(max_workers)
    pool.start()
    return pool
