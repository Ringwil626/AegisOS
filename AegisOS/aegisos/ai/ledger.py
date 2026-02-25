"""AI Cost Governance Layer - Phase 5.

Budget enforcement and usage tracking for AI calls.
No access to system_state. No bypass of executor.
"""
import sqlite3
import os
import time

DB_PATH = os.path.abspath("aegisos.db")

# Pricing: (input_price_per_1M, output_price_per_1M) in CNY (人民币)
# Source: https://platform.moonshot.cn/docs/pricing/chat
# Updated: 2026-02-17
MODEL_PRICING = {
    # kimi-k2.5: 256k上下文，多模态，Agent能力
    # 输入缓存命中: ¥0.70/M, 缓存未命中: ¥4.00/M, 输出: ¥21.00/M
    "kimi-k2.5": (2.35, 21.00),  # 输入取平均(命中/未命中)，输出固定
    
    # 保留旧别名兼容
    "kimi": (2.35, 21.00),
    
    # 其他可选模型 (如需降级使用)
    # "moonshot-v1-8k": (2.00, 10.00),      # 基础版，更便宜
    # "kimi-k2-thinking": (2.50, 16.00),    # 推理版，中等价格
}

# ============================================================================
# Budget Limits (基于月预算 ¥200 计算)
# ============================================================================
# 计算依据:
#   - 月预算: ¥200
#   - 日预算: ¥200 / 30 ≈ ¥6.67，保守取 ¥5 (留 25% 缓冲)
#   - kimi-k2.5 单次任务平均成本: 
#       输入 10K tokens + 输出 5K tokens ≈ ¥0.15
#   - 日可执行任务: ¥5 / ¥0.15 ≈ 33 次
#
# Token 限制:
#   - 单次任务: 25K tokens (约 ¥0.35，防止单次爆炸)
#   - 每小时: 40K tokens (防止短时突发)
#   - 每日: 150K tokens (对应 ¥5 预算)
# ============================================================================

TASK_TOKEN_LIMIT = 25_000      # 单次任务 25K tokens (约 ¥0.35)
HOURLY_TOKEN_LIMIT = 40_000    # 每小时 40K tokens (防突发)
DAILY_TOKEN_LIMIT = 150_000    # 每日 150K tokens (约 ¥5)

# 月度硬上限 (安全网)
MONTHLY_TOKEN_LIMIT = 4_500_000  # 150K * 30 = 4.5M (约 ¥150-200)


def init_ai_ledger():
    """Initialize ai_ledger table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ai_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            estimated_cost REAL,
            status TEXT,
            created_at REAL DEFAULT (unixepoch())
        )
    """)
    conn.commit()
    conn.close()


def get_daily_usage(model: str = None) -> int:
    """Get total tokens used today (since midnight)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    day_start = time.time() - (time.time() % 86400)
    
    if model:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE model = ? AND created_at > ? AND status IN ('completed', 'committed')",
            (model, day_start)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE created_at > ? AND status IN ('completed', 'committed')",
            (day_start,)
        )
    
    result = cursor.fetchone()[0]
    conn.close()
    return result


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost for AI call."""
    if model not in MODEL_PRICING:
        return 0.0
    
    input_price, output_price = MODEL_PRICING[model]
    input_cost = (prompt_tokens / 1_000_000) * input_price
    output_cost = (completion_tokens / 1_000_000) * output_price
    return round(input_cost + output_cost, 6)


def get_hourly_usage(model: str = None) -> int:
    """Get total tokens used in last hour."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    hour_ago = time.time() - 3600
    
    if model:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE model = ? AND created_at > ? AND status IN ('completed', 'committed')",
            (model, hour_ago)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE created_at > ? AND status IN ('completed', 'committed')",
            (hour_ago,)
        )
    
    result = cursor.fetchone()[0]
    conn.close()
    return result


def get_monthly_usage(model: str = None) -> int:
    """Get total tokens used this month (since 1st)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取本月1日0点的时间戳
    now = time.time()
    local_time = time.localtime(now)
    month_start = time.mktime((local_time.tm_year, local_time.tm_mon, 1, 0, 0, 0, 0, 0, 0))
    
    if model:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE model = ? AND created_at > ? AND status IN ('completed', 'committed')",
            (model, month_start)
        )
    else:
        cursor.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) FROM ai_ledger WHERE created_at > ? AND status IN ('completed', 'committed')",
            (month_start,)
        )
    
    result = cursor.fetchone()[0]
    conn.close()
    return result


def check_daily_budget(model: str, estimated_tokens: int) -> tuple[bool, str]:
    """Check if AI call is within budget. Three-layer guard.
    
    Returns: (allowed, reason)
    """
    # Layer 1: Per-task limit
    if estimated_tokens > TASK_TOKEN_LIMIT:
        return False, f"Task token limit exceeded: {estimated_tokens} > {TASK_TOKEN_LIMIT}"
    
    # Layer 2: Hourly limit (burst protection)
    hourly_used = get_hourly_usage(model)
    if hourly_used + estimated_tokens > HOURLY_TOKEN_LIMIT:
        return False, f"Hourly budget exceeded: {hourly_used} + {estimated_tokens} > {HOURLY_TOKEN_LIMIT}"
    
    # Layer 3: Daily limit
    daily_used = get_daily_usage(model)
    if daily_used + estimated_tokens > DAILY_TOKEN_LIMIT:
        return False, f"Daily budget exceeded: {daily_used} + {estimated_tokens} > {DAILY_TOKEN_LIMIT}"
    
    # Layer 4: Monthly hard limit (safety net)
    monthly_used = get_monthly_usage(model)
    if monthly_used + estimated_tokens > MONTHLY_TOKEN_LIMIT:
        return False, f"Monthly budget exceeded: {monthly_used} + {estimated_tokens} > {MONTHLY_TOKEN_LIMIT}"
    
    return True, ""


def log_ai_usage(task_id: int, model: str, prompt_tokens: int, 
                 completion_tokens: int, status: str = "committed") -> int:
    """Log AI usage to ledger. Called after AI response or on rejection.
    
    Args:
        task_id: Associated task ID
        model: Model name
        prompt_tokens: Input tokens
        completion_tokens: Output tokens  
        status: 'committed', 'rejected', 'completed'
    
    Returns:
        ledger entry ID
    """
    total_tokens = prompt_tokens + completion_tokens
    estimated_cost = estimate_cost(model, prompt_tokens, completion_tokens)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO ai_ledger 
           (task_id, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, unixepoch())""",
        (task_id, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost, status)
    )
    ledger_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return ledger_id


def get_ledger_entry(ledger_id: int) -> dict | None:
    """Get single ledger entry."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, task_id, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost, status, created_at FROM ai_ledger WHERE id = ?",
        (ledger_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "task_id": row[1],
            "model": row[2],
            "prompt_tokens": row[3],
            "completion_tokens": row[4],
            "total_tokens": row[5],
            "estimated_cost": row[6],
            "status": row[7],
            "created_at": row[8]
        }
    return None


def get_task_ledger_summary(task_id: int) -> dict:
    """Get cost summary for a task."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COALESCE(SUM(total_tokens), 0), COALESCE(SUM(estimated_cost), 0), COUNT(*) FROM ai_ledger WHERE task_id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_tokens": row[0],
        "total_cost": row[1],
        "call_count": row[2]
    }


def get_budget_report() -> dict:
    """Get comprehensive budget usage report.
    
    Returns dict with usage and limits for all time windows.
    """
    hourly_used = get_hourly_usage()
    daily_used = get_daily_usage()
    monthly_used = get_monthly_usage()
    
    # 估算成本 (使用kimi-k2.5平均价格)
    avg_input_price = 2.35  # CNY per 1M
    avg_output_price = 21.00  # CNY per 1M
    
    # 估算当前消耗的成本 (假设输入:输出 = 2:1)
    hourly_cost = (hourly_used * 0.667 / 1_000_000 * avg_input_price + 
                   hourly_used * 0.333 / 1_000_000 * avg_output_price)
    daily_cost = (daily_used * 0.667 / 1_000_000 * avg_input_price + 
                  daily_used * 0.333 / 1_000_000 * avg_output_price)
    monthly_cost = (monthly_used * 0.667 / 1_000_000 * avg_input_price + 
                    monthly_used * 0.333 / 1_000_000 * avg_output_price)
    
    return {
        "hourly": {
            "used": hourly_used,
            "limit": HOURLY_TOKEN_LIMIT,
            "remaining": HOURLY_TOKEN_LIMIT - hourly_used,
            "percent": round(hourly_used / HOURLY_TOKEN_LIMIT * 100, 1),
            "est_cost_cny": round(hourly_cost, 2)
        },
        "daily": {
            "used": daily_used,
            "limit": DAILY_TOKEN_LIMIT,
            "remaining": DAILY_TOKEN_LIMIT - daily_used,
            "percent": round(daily_used / DAILY_TOKEN_LIMIT * 100, 1),
            "est_cost_cny": round(daily_cost, 2)
        },
        "monthly": {
            "used": monthly_used,
            "limit": MONTHLY_TOKEN_LIMIT,
            "remaining": MONTHLY_TOKEN_LIMIT - monthly_used,
            "percent": round(monthly_used / MONTHLY_TOKEN_LIMIT * 100, 1),
            "est_cost_cny": round(monthly_cost, 2)
        },
        "task_limit": TASK_TOKEN_LIMIT
    }


def format_budget_report() -> str:
    """Format budget report as human-readable string."""
    report = get_budget_report()
    
    h = report["hourly"]
    d = report["daily"]
    m = report["monthly"]
    
    # 状态表情
    h_emoji = "🟢" if h["percent"] < 50 else ("🟡" if h["percent"] < 80 else "🔴")
    d_emoji = "🟢" if d["percent"] < 50 else ("🟡" if d["percent"] < 80 else "🔴")
    m_emoji = "🟢" if m["percent"] < 50 else ("🟡" if m["percent"] < 80 else "🔴")
    
    return f"""💰 AI Budget Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{h_emoji} Hourly:  {h['used']:,} / {h['limit']:,} ({h['percent']}%) ~¥{h['est_cost_cny']}
{d_emoji} Daily:   {d['used']:,} / {d['limit']:,} ({d['percent']}%) ~¥{d['est_cost_cny']}
{m_emoji} Monthly: {m['used']:,} / {m['limit']:,} ({m['percent']}%) ~¥{m['est_cost_cny']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task Limit: {report['task_limit']:,} tokens/call
Model: kimi-k2.5 (¥2.35/¥21.00 per 1M)
Monthly Budget: ¥200 (~¥5/day)
"""
