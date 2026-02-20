"""AI Pricing - Local pricing table for deterministic cost calculation.

Phase5: AI Usage Accounting
- Prices defined in code (no external dependencies)
- Deterministic cost calculation
- Supports multiple providers and models
"""
from typing import Dict, Tuple

# Pricing table - defined in code for zero dependencies
PRICING_TABLE = {
    "moonshot": {
        "kimi-k2.5": {
            "input_per_1k": 0.012,
            "output_per_1k": 0.012,
            "currency": "USD"
        },
        "kimi-k1.5": {
            "input_per_1k": 0.008,
            "output_per_1k": 0.008,
            "currency": "USD"
        },
        "default": {
            "input_per_1k": 0.012,
            "output_per_1k": 0.012,
            "currency": "USD"
        }
    },
    "openai": {
        "gpt-4": {
            "input_per_1k": 0.03,
            "output_per_1k": 0.06,
            "currency": "USD"
        },
        "gpt-3.5-turbo": {
            "input_per_1k": 0.0015,
            "output_per_1k": 0.002,
            "currency": "USD"
        },
        "default": {
            "input_per_1k": 0.03,
            "output_per_1k": 0.06,
            "currency": "USD"
        }
    },
    "default": {
        "input_per_1k": 0.012,
        "output_per_1k": 0.012,
        "currency": "USD"
    }
}


def get_model_pricing(model: str, provider: str = "moonshot") -> Dict[str, float]:
    """Get pricing for specific model.
    
    Args:
        model: Model name (e.g., "kimi-k2.5")
        provider: Provider name (e.g., "moonshot")
        
    Returns:
        Dict with input_per_1k, output_per_1k
    """
    # Try specific provider + model
    if provider in PRICING_TABLE and model in PRICING_TABLE[provider]:
        return {
            "input_per_1k": PRICING_TABLE[provider][model].get("input_per_1k", 0.012),
            "output_per_1k": PRICING_TABLE[provider][model].get("output_per_1k", 0.012),
            "currency": PRICING_TABLE[provider][model].get("currency", "USD")
        }
    
    # Try provider default
    if provider in PRICING_TABLE and "default" in PRICING_TABLE[provider]:
        return {
            "input_per_1k": PRICING_TABLE[provider]["default"].get("input_per_1k", 0.012),
            "output_per_1k": PRICING_TABLE[provider]["default"].get("output_per_1k", 0.012),
            "currency": PRICING_TABLE[provider]["default"].get("currency", "USD")
        }
    
    # Fall back to global default
    default = PRICING_TABLE.get("default", {})
    return {
        "input_per_1k": default.get("input_per_1k", 0.012),
        "output_per_1k": default.get("output_per_1k", 0.012),
        "currency": default.get("currency", "USD")
    }


def calculate_cost(
    model: str,
    tokens_prompt: int,
    tokens_completion: int,
    provider: str = "moonshot"
) -> Tuple[float, str]:
    """Calculate estimated cost for AI usage.
    
    Phase5: Cost calculated immediately in Executor
    - No online price fetching
    - Deterministic calculation
    
    Args:
        model: Model name
        tokens_prompt: Input tokens
        tokens_completion: Output tokens
        provider: Provider name
        
    Returns:
        (cost_estimate, currency)
    """
    pricing = get_model_pricing(model, provider)
    
    input_cost = (tokens_prompt / 1000) * pricing["input_per_1k"]
    output_cost = (tokens_completion / 1000) * pricing["output_per_1k"]
    total_cost = input_cost + output_cost
    
    return round(total_cost, 6), pricing["currency"]


def format_cost(cost: float, currency: str = "USD") -> str:
    """Format cost for display."""
    if currency == "USD":
        return f"${cost:.4f}"
    return f"{cost:.4f} {currency}"


# Convenience functions

def get_kimi_pricing(model: str = "kimi-k2.5") -> Dict[str, float]:
    """Get pricing for Kimi models."""
    return get_model_pricing(model, provider="moonshot")


def estimate_cost_simple(tokens_total: int, model: str = "kimi-k2.5") -> float:
    """Simple cost estimation using average price."""
    pricing = get_model_pricing(model)
    avg_price = (pricing["input_per_1k"] + pricing["output_per_1k"]) / 2
    return round((tokens_total / 1000) * avg_price, 6)
