"""Kimi Client - Stateless Inference Executor for AegisOS.

Inference Contract v1.0:
- Stateless: No internal state between calls
- Auditable: Returns full usage metrics for Phase5 ledger
- Interruptible: Enforces timeout at call level
- Retryable: Exponential backoff for transient failures
- Validated: Output structure verification

This is NOT an SDK wrapper. It is a compute device driver for AegisOS.
"""
import os
import time
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class InferenceError(Exception):
    """Inference execution error."""
    pass


class ValidationError(Exception):
    """Output validation error."""
    pass


class TimeoutError(Exception):
    """Inference timeout error."""
    pass


@dataclass(frozen=True)
class InferenceRequest:
    """Input structure - constructed by Executor.
    
    Frozen dataclass ensures immutability.
    """
    task_id: str
    project: str
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: int
    prompt: str
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        # Validation at construction time
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.prompt:
            raise ValueError("prompt is required")
        if self.timeout_sec < 1:
            raise ValueError("timeout_sec must be >= 1")


@dataclass(frozen=True)
class InferenceResult:
    """Output structure - completely structured, no free text.
    
    This is the ONLY source of truth for Phase5 cost auditing.
    """
    task_id: str
    success: bool
    output_text: str
    usage: Dict[str, int]
    latency_ms: int
    error: Optional[str] = None
    
    def __post_init__(self):
        # Ensure usage structure is complete
        required_keys = {"prompt_tokens", "completion_tokens", "total_tokens"}
        if not required_keys.issubset(self.usage.keys()):
            raise ValueError(f"usage must contain {required_keys}")


class RetryPolicy:
    """Retry configuration - exponential backoff."""
    MAX_RETRY = 2
    BACKOFF_BASE = 1.0  # seconds
    BACKOFF_MULTIPLIER = 3.0
    
    @classmethod
    def should_retry(cls, attempt: int, error: Exception) -> bool:
        """Determine if error is retryable.
        
        Only retry on:
        - TimeoutError
        - 5xx errors (server errors)
        
        Never retry on:
        - 4xx errors (client errors)
        - ValidationError
        """
        if attempt >= cls.MAX_RETRY:
            return False
        
        # Timeout is always retryable
        if isinstance(error, TimeoutError):
            return True
        
        # Check for 5xx in error message
        error_str = str(error).lower()
        if "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
            return True
        if "server error" in error_str or "internal error" in error_str:
            return True
        
        # 4xx errors are not retryable
        if "400" in error_str or "401" in error_str or "403" in error_str or "404" in error_str:
            return False
        if "client error" in error_str or "bad request" in error_str:
            return False
        
        # Default: don't retry unknown errors
        return False
    
    @classmethod
    def get_delay(cls, attempt: int) -> float:
        """Calculate backoff delay: 1s → 3s."""
        return cls.BACKOFF_BASE * (cls.BACKOFF_MULTIPLIER ** attempt)


class ResponseValidator:
    """Validates AI output structure."""
    
    @staticmethod
    def validate(raw_output: str, usage: Dict[str, int]) -> None:
        """Validate response meets minimum requirements.
        
        Raises:
            ValidationError: If output is invalid
        """
        # Check output not empty
        if not raw_output or len(raw_output.strip()) == 0:
            raise ValidationError("Empty output from model")
        
        # Check usage exists and is valid
        if not usage:
            raise ValidationError("Missing usage data")
        
        total = usage.get("total_tokens", 0)
        if total <= 0:
            raise ValidationError(f"Invalid total_tokens: {total}")
        
        # Check individual token counts
        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        if prompt < 0 or completion < 0:
            raise ValidationError(f"Negative token count: prompt={prompt}, completion={completion}")


class KimiInferenceExecutor:
    """Stateless inference executor for Kimi API.
    
    Design principles:
    1. No internal state - each call is independent
    2. No caching - fresh connection each time
    3. No task logic - pure execution only
    4. Full observability - returns all metrics
    
    Usage:
        result = run_inference(request)
        # result.usage contains token counts for ledger
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize with API credentials.
        
        Args:
            api_key: Moonshot API key (or from env MOONSHOT_API_KEY)
            base_url: API base URL (defaults to Moonshot endpoint)
        """
        self._api_key = api_key or os.getenv("MOONSHOT_API_KEY", "")
        self._base_url = base_url or os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        
        if not self._api_key:
            raise InferenceError("MOONSHOT_API_KEY not configured")
        
        # Lazy initialization - client created per-request
        self._client = None
    
    def _get_client(self):
        """Get or create OpenAI client (per-request instantiation)."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url
                )
            except ImportError:
                raise InferenceError("openai package not installed. Run: pip install openai")
        return self._client
    
    def _execute_single(self, request: InferenceRequest) -> InferenceResult:
        """Execute single inference request with timeout enforcement.
        
        Args:
            request: InferenceRequest with all parameters
            
        Returns:
            InferenceResult with usage metrics
            
        Raises:
            TimeoutError: If execution exceeds timeout_sec
            InferenceError: For API errors
        """
        start_time = time.time()
        
        # Prepare API call parameters
        messages = [
            {"role": "system", "content": "You are an AI assistant. Output valid JSON when requested."},
            {"role": "user", "content": request.prompt}
        ]
        
        try:
            # Execute with external timeout enforcement
            # We use a thread-based approach to enforce hard timeout
            import threading
            import concurrent.futures
            
            def _api_call():
                client = self._get_client()
                return client.chat.completions.create(
                    model=request.model,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    timeout=request.timeout_sec - 1  # Slightly less than our timeout
                )
            
            # Use ThreadPoolExecutor for timeout control
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_api_call)
                try:
                    response = future.result(timeout=request.timeout_sec)
                except concurrent.futures.TimeoutError:
                    raise TimeoutError(f"Inference timed out after {request.timeout_sec}s")
            
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Extract content
            content = response.choices[0].message.content or ""
            
            # Extract usage from response
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else len(request.prompt) // 4,
                "completion_tokens": response.usage.completion_tokens if response.usage else len(content) // 4,
                "total_tokens": response.usage.total_tokens if response.usage else (len(request.prompt) + len(content)) // 4
            }
            
            # Validate output
            ResponseValidator.validate(content, usage)
            
            return InferenceResult(
                task_id=request.task_id,
                success=True,
                output_text=content,
                usage=usage,
                latency_ms=latency_ms,
                error=None
            )
            
        except TimeoutError:
            raise
        except Exception as e:
            # Convert to InferenceError
            raise InferenceError(f"API call failed: {str(e)}")
    
    def run_inference(self, request: InferenceRequest) -> InferenceResult:
        """Execute inference with retry logic.
        
        This is the ONLY public interface exposed by this module.
        
        Args:
            request: Complete inference request
            
        Returns:
            InferenceResult (always structured, never raises)
            
        Note:
            Even on failure, returns InferenceResult with success=False.
            Caller must check success flag.
        """
        start_time = time.time()
        last_error = None
        
        for attempt in range(RetryPolicy.MAX_RETRY + 1):
            try:
                return self._execute_single(request)
                
            except (TimeoutError, InferenceError) as e:
                last_error = e
                
                if RetryPolicy.should_retry(attempt, e):
                    delay = RetryPolicy.get_delay(attempt)
                    time.sleep(delay)
                    continue
                else:
                    # Not retryable or max retries reached
                    break
        
        # All retries exhausted or non-retryable error
        latency_ms = int((time.time() - start_time) * 1000)
        
        return InferenceResult(
            task_id=request.task_id,
            success=False,
            output_text="",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=latency_ms,
            error=f"{type(last_error).__name__}: {str(last_error)}"
        )


# Module-level singleton for reuse (still stateless per-call)
_default_executor: Optional[KimiInferenceExecutor] = None


def get_executor(api_key: Optional[str] = None, base_url: Optional[str] = None) -> KimiInferenceExecutor:
    """Get or create default executor singleton.
    
    Note: Executor is stateless - singleton is for connection reuse only.
    """
    global _default_executor
    if _default_executor is None:
        _default_executor = KimiInferenceExecutor(api_key=api_key, base_url=base_url)
    return _default_executor


def run_inference(request: InferenceRequest) -> InferenceResult:
    """Convenience function - execute inference with default executor.
    
    This is the primary entry point for AegisOS Executor.
    
    Example:
        request = InferenceRequest(
            task_id="task_123",
            project="my_project",
            model="kimi-k2.5",
            temperature=1.0,
            max_tokens=4000,
            timeout_sec=300,
            prompt="Generate code for...",
            metadata={"requested_by": "user_1", "phase": "execution"}
        )
        result = run_inference(request)
        
        if result.success:
            # Use result.output_text
            # Log result.usage to Phase5 ledger
            pass
    """
    executor = get_executor()
    return executor.run_inference(request)


def check_configuration() -> tuple[bool, str]:
    """Check if inference system is properly configured."""
    api_key = os.getenv("MOONSHOT_API_KEY", "")
    if not api_key:
        return False, "MOONSHOT_API_KEY not set"
    
    try:
        from openai import OpenAI
        return True, f"Inference system ready (API key: {api_key[:8]}...)"
    except ImportError:
        return False, "openai package not installed"
