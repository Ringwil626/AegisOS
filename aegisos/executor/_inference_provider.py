"""Inference Provider - Internal implementation for inference_executor.

This is NOT a public API. Only inference_executor should import this.
"""
import os
import time
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass(frozen=True)
class InferenceRequest:
    task_id: str
    project: str
    model: str
    temperature: float
    max_tokens: int
    timeout_sec: int
    prompt: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass(frozen=True)
class InferenceResult:
    task_id: str
    success: bool
    output_text: str
    usage: Dict[str, int]
    latency_ms: int
    error: Optional[str]

def run_inference(request: InferenceRequest) -> InferenceResult:
    """Execute inference with provider routing."""
    start = time.time()
    
    # Check for mock mode
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        # Mock mode for testing
        return _mock_inference(request)
    
    # Real API call
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")
        
        response = client.chat.completions.create(
            model=request.model,
            messages=[{"role": "user", "content": request.prompt}],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            timeout=request.timeout_sec
        )
        
        latency_ms = int((time.time() - start) * 1000)
        
        return InferenceResult(
            task_id=request.task_id,
            success=True,
            output_text=response.choices[0].message.content,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0
            },
            latency_ms=latency_ms,
            error=None
        )
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return InferenceResult(
            task_id=request.task_id,
            success=False,
            output_text="",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=latency_ms,
            error=str(e)
        )

def _mock_inference(request: InferenceRequest) -> InferenceResult:
    """Mock inference for testing without API key."""
    time.sleep(0.1)  # Simulate latency
    
    mock_response = json.dumps({
        "status": "success",
        "action": "mock_execute",
        "result": {"message": "Mock execution (MOONSHOT_API_KEY not set)"}
    })
    
    return InferenceResult(
        task_id=request.task_id,
        success=True,
        output_text=mock_response,
        usage={
            "prompt_tokens": len(request.prompt) // 4,
            "completion_tokens": len(mock_response) // 4,
            "total_tokens": (len(request.prompt) + len(mock_response)) // 4
        },
        latency_ms=100,
        error=None
    )

def check_configuration():
    """Check if inference system is configured."""
    api_key = os.getenv("MOONSHOT_API_KEY")
    if not api_key:
        return False, "MOONSHOT_API_KEY not set (running in mock mode)"
    return True, f"Inference configured (model: kimi-k2.5)"
