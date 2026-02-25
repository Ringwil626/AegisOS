"""Policy Loader - Phase6 Policy Configuration.

Loads and validates policy.yaml configuration for:
- Analyzer scan intervals
- Evaluator thresholds
- Optimization triggers
- Shadow validation criteria
"""
import os
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)


@dataclass
class PolicyConfig:
    """Policy configuration structure."""
    # Analysis settings
    scan_interval_minutes: int
    metrics_window_hours: int
    
    # Evaluation thresholds
    token_drift_pct: float
    retry_ratio: float
    latency_p95_sec: float
    min_sample_size: int
    cooldown_minutes: int
    
    # Shadow validation
    min_shadow_runs: int
    max_shadow_duration_hours: int
    success_rate_regression_threshold: float


class PolicyLoader:
    """Loads and caches policy configuration."""
    
    _config: Optional[PolicyConfig] = None
    _config_path: str = os.path.join(_project_root, "config", "policy.yaml")
    
    @classmethod
    def load_policy(cls) -> PolicyConfig:
        """Load policy from YAML or use defaults."""
        if cls._config is not None:
            return cls._config
        
        if os.path.exists(cls._config_path):
            try:
                import yaml
                with open(cls._config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            except ImportError:
                data = {}
        else:
            data = {}
        
        # Extract values with defaults
        optimize_when = data.get('optimize_when', {})
        
        cls._config = PolicyConfig(
            scan_interval_minutes=data.get('scan_interval_minutes', 10),
            metrics_window_hours=data.get('metrics_window_hours', 24),
            token_drift_pct=optimize_when.get('token_drift_pct', 25),
            retry_ratio=optimize_when.get('retry_ratio', 0.2),
            latency_p95_sec=optimize_when.get('latency_p95_sec', 12),
            min_sample_size=data.get('min_sample_size', 20),
            cooldown_minutes=data.get('cooldown_minutes', 60),
            min_shadow_runs=data.get('min_shadow_runs', 10),
            max_shadow_duration_hours=data.get('max_shadow_duration_hours', 24),
            success_rate_regression_threshold=data.get('success_rate_regression_threshold', 0.05)
        )
        
        return cls._config
    
    @classmethod
    def reload_policy(cls) -> PolicyConfig:
        """Force reload policy from disk."""
        cls._config = None
        return cls.load_policy()
    
    @classmethod
    def get_default_policy_yaml(cls) -> str:
        """Get default policy YAML content."""
        return """# AegisOS Phase6 Policy Configuration
# Controls when and how system optimizations are triggered

# Analyzer settings
scan_interval_minutes: 10
metrics_window_hours: 24

# Evaluator thresholds
optimize_when:
  token_drift_pct: 25        # Token usage increase threshold (%)
  retry_ratio: 0.2          # Retry ratio threshold (0-1)
  latency_p95_sec: 12       # P95 latency threshold (seconds)
  success_rate_drop: 0.15   # Success rate drop threshold (0-1)

# Evaluation constraints
min_sample_size: 20         # Minimum tasks for analysis
cooldown_minutes: 60        # Cooldown between proposals

# Shadow validation
min_shadow_runs: 10         # Minimum shadow runs before switch
max_shadow_duration_hours: 24
success_rate_regression_threshold: 0.05  # Max allowed regression
"""
    
    @classmethod
    def create_default_policy(cls):
        """Create default policy.yaml if not exists."""
        config_dir = os.path.dirname(cls._config_path)
        os.makedirs(config_dir, exist_ok=True)
        
        if not os.path.exists(cls._config_path):
            with open(cls._config_path, 'w', encoding='utf-8') as f:
                f.write(cls.get_default_policy_yaml())
            print(f"[Policy] Created default policy at {cls._config_path}")


def get_policy() -> PolicyConfig:
    """Convenience function to get policy config."""
    return PolicyLoader.load_policy()


def check_cooldown(last_proposal_time: Optional[float], 
                   cooldown_minutes: int = 60) -> bool:
    """Check if cooldown period has passed.
    
    Args:
        last_proposal_time: Timestamp of last proposal
        cooldown_minutes: Cooldown duration
        
    Returns:
        True if cooldown passed or no previous proposal
    """
    if last_proposal_time is None:
        return True
    
    import time
    elapsed_minutes = (time.time() - last_proposal_time) / 60
    return elapsed_minutes >= cooldown_minutes
