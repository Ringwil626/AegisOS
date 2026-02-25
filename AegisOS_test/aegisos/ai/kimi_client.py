"""Kimi API Client - Moonshot AI integration.

Step 1: 准备 Kimi API 客户端
统一调用 Kimi API，所有任务都通过 run_task() 发送
结果必须是 JSON Action Schema，以防 AI 输出不规范
"""
import os
import json
from typing import Optional, Dict, Any


class KimiClient:
    """Kimi API client for AegisOS integration."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.moonshot.cn/v1"):
        """Initialize Kimi client.
        
        Args:
            api_key: Kimi API key
            base_url: API endpoint URL
        """
        self.api_key = api_key
        self.base_url = base_url
        
        # Initialize OpenAI client
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
    
    def run_task(self, prompt: str, context: dict = None) -> dict:
        """调用 Kimi API 执行任务.
        
        Step 2: 项目上下文封装
        AegisOS 为每个项目维护：
        - agent.md（角色/指令模板）
        - 历史修改索引 history/
        - 项目描述文件 project_desc.md
        
        Args:
            prompt: 打包后的自然语言指令 + 项目上下文
            context: 可选，额外信息如 memory, project config
                    包含字段：
                    - project_name: 项目名
                    - agent_md: agent.md 路径
                    - history_index: history/ 目录路径
                    - project_desc: project_desc.md 路径
                    - memory: 相关历史任务列表
                    - priority: 任务优先级
                    - token_quota: 剩余 token 配额
                    - shadow_run: 是否影子运行
        
        Returns:
            JSON Action Schema
        """
        # Step 2: 封装成 prompt
        full_prompt = self._build_prompt(prompt, context)
        
        # Step 3: 调用 Kimi API
        import time
        
        model = os.getenv("MOONSHOT_MODEL", "kimi-k2.5")
        max_tokens = int(os.getenv("MOONSHOT_MAX_TOKENS", "4000"))
        
        response = self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an AI assistant that only outputs valid JSON Action Schema."},
                {"role": "user", "content": full_prompt}
            ],
            temperature=1.0,  # kimi-k2.5 requires temperature=1.0
            max_tokens=max_tokens,
            response_format={"type": "json_object"}  # Force JSON output
        )
        
        # Parse response
        content = response.choices[0].message.content
        result = json.loads(content)
        
        # Ensure Action Schema structure
        if "actions" not in result:
            result["actions"] = []
        if "explanation" not in result:
            result["explanation"] = ""
        if "risk_level" not in result:
            result["risk_level"] = "medium"
        
        return result
    
    def _build_prompt(self, instruction: str, context: dict = None) -> str:
        """Step 2: 项目上下文封装.
        
        封装成 prompt 格式：
        Project: {project_name}
        Agent Index: {project_path}/agent.md
        History Index: {project_path}/history/
        Project Description: {project_path}/project_desc.md
        
        Instruction: {user_command}
        """
        ctx = context or {}
        
        prompt_parts = []
        
        # Project context
        if "project_name" in ctx:
            prompt_parts.append(f"Project: {ctx['project_name']}")
        
        if "agent_md" in ctx:
            prompt_parts.append(f"Agent Index: {ctx['agent_md']}")
        
        if "history_index" in ctx:
            prompt_parts.append(f"History Index: {ctx['history_index']}")
        
        if "project_desc" in ctx:
            prompt_parts.append(f"Project Description: {ctx['project_desc']}")
        
        # Memory context
        if "memory" in ctx and ctx["memory"]:
            prompt_parts.append("\nRelevant Historical Context:")
            for i, mem in enumerate(ctx["memory"][:5], 1):
                prompt_parts.append(f"  [{i}] {mem}")
        
        # Execution constraints
        constraints = []
        if ctx.get("priority"):
            constraints.append(f"Priority: {ctx['priority']}")
        if ctx.get("token_quota"):
            constraints.append(f"Token Quota: {ctx['token_quota']}")
        if ctx.get("shadow_run"):
            constraints.append("Mode: SHADOW_RUN")
        
        if constraints:
            prompt_parts.append("\nExecution Constraints:")
            for c in constraints:
                prompt_parts.append(f"  - {c}")
        
        # Instruction
        prompt_parts.append(f"\nInstruction: {instruction}")
        
        # Output format (JSON Action Schema)
        output_instruction = """
You must respond with a JSON Action Schema in the following format:
{
  "actions": [
    {"type": "edit_file", "file": "path/to/file", "content": "new content"},
    {"type": "create_file", "file": "path/to/file", "content": "file content"},
    {"type": "update_memory", "key": "memory_key", "value": "memory_value"},
    {"type": "shell_command", "command": "safe_command", "timeout": 30}
  ],
  "explanation": "Brief explanation of the changes",
  "risk_level": "low|medium|high"
}

Valid action types:
- edit_file: Modify an existing file
- create_file: Create a new file
- delete_file: Delete a file
- update_memory: Store information in project memory
- shell_command: Execute a safe shell command (limited to project directory)

DO NOT include any text outside the JSON structure.
"""
        prompt_parts.append(output_instruction)
        
        return "\n".join(prompt_parts)


# Module-level convenience functions

_kimi_client: Optional[KimiClient] = None


def get_client(api_key: Optional[str] = None) -> KimiClient:
    """Get or create KimiClient singleton."""
    global _kimi_client
    if _kimi_client is None:
        key = api_key or os.getenv("MOONSHOT_API_KEY", "")
        base = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        if not key:
            raise RuntimeError("MOONSHOT_API_KEY not configured")
        _kimi_client = KimiClient(api_key=key, base_url=base)
    return _kimi_client


def kimi_call(prompt: str) -> tuple[str, int, int]:
    """Interface compatible with execute_with_budget_guard().
    
    This function adapts run_task() to the simpler signature used by budget guard.
    
    Args:
        prompt: Raw prompt string (can include context via ||| separator)
    
    Returns:
        (json_response_string, prompt_tokens, completion_tokens)
    """
    client = get_client()
    
    # Parse prompt and context if separated by |||
    if "|||" in prompt:
        instruction, context_json = prompt.split("|||", 1)
        context = json.loads(context_json)
    else:
        instruction = prompt
        context = {}
    
    result = client.run_task(instruction, context)
    response_json = json.dumps(result)
    
    # Estimate tokens (approximate)
    prompt_tokens = len(prompt) // 4
    completion_tokens = len(response_json) // 4
    
    return response_json, prompt_tokens, completion_tokens


def check_configuration() -> tuple[bool, str]:
    """Check if Kimi client is properly configured."""
    api_key = os.getenv("MOONSHOT_API_KEY", "")
    if not api_key:
        return False, "MOONSHOT_API_KEY not set"
    return True, f"Kimi client configured (API key: {api_key[:8]}...)"
