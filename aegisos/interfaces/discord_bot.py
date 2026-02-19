"""Discord bot - Runtime Transition Protocol v1.0 + Phase 6 Evolution.

Commands:
    /status  - Display system state and supervisor status
    /wake    - Start supervisor (system_state.status = running)
    /stop    - Stop supervisor (system_state.status = stopped)
    /task    - Record new task intent
    /evolve  - Request AI evolution (Phase 6)
    /approve - Approve evolution proposal (Phase 6)
    /reject  - Reject evolution proposal (Phase 6)
"""
import discord
from discord import app_commands
from discord.ext import commands
import os
import sys

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import (
    get_system_state,
    create_task,
    get_last_heartbeat,
    list_evolution_jobs,
    update_evolution_job_status,
    get_evolution_job,
    write_audit_log,
    get_latest_health_metrics,
    get_memory_statistics,
    get_ai_budget
)
from aegisos.core import supervisor
from aegisos.evolution.manager import create_evolution_proposal, list_proposals

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")


@bot.event
async def on_ready():
    """Sync slash commands on ready."""
    print(f"Discord bot logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="status", description="Get AegisOS system status")
async def status_command(interaction: discord.Interaction):
    """Display system state and supervisor status."""
    system_status = get_system_state("status") or "unknown"
    runtime_version = get_system_state("runtime_version") or "unknown"
    target_version = get_system_state("target_version") or "none"
    supervisor_running = supervisor.is_running()
    
    # Get last heartbeat
    hb = get_last_heartbeat("supervisor")
    hb_msg = hb["message"] if hb else "none"
    hb_ts = hb["timestamp"] if hb else 0
    
    await interaction.response.send_message(
        f"**AegisOS Status**\n"
        f"System: {system_status}\n"
        f"Runtime: {runtime_version}\n"
        f"Target: {target_version}\n"
        f"Supervisor: {'running' if supervisor_running else 'stopped'}\n"
        f"Last HB: {hb_msg}"
    )


@bot.tree.command(name="wake", description="Start AegisOS supervisor")
async def wake_command(interaction: discord.Interaction):
    """Start supervisor - sets system_state to running."""
    actor = str(interaction.user)
    
    if supervisor.is_running():
        await interaction.response.send_message(
            "Supervisor already running.",
            ephemeral=True
        )
        write_audit_log(actor, "/wake", "rejected", "Already running")
        return
    
    supervisor.start()
    write_audit_log(actor, "/wake", "success", "Supervisor started")
    await interaction.response.send_message("Supervisor started.")


@bot.tree.command(name="stop", description="Stop AegisOS supervisor")
async def stop_command(interaction: discord.Interaction):
    """Stop supervisor - sets system_state to stopped."""
    actor = str(interaction.user)
    
    if not supervisor.is_running():
        await interaction.response.send_message(
            "Supervisor not running.",
            ephemeral=True
        )
        write_audit_log(actor, "/stop", "rejected", "Not running")
        return
    
    supervisor.stop()
    write_audit_log(actor, "/stop", "success", "Supervisor stopped")
    await interaction.response.send_message("Supervisor stopped.")


@bot.tree.command(name="task", description="Record and execute a new task")
@app_commands.describe(text="Task description (prefix with 'ai ' or 'kimi ' for AI)")
async def task_command(interaction: discord.Interaction, text: str):
    """Record new task intent and execute.
    
    AI prefixes (case-insensitive):
    - ai: / ai：/ ai␣ (space)
    - kimi: / kimi：/ kimi␣ (space)
    """
    actor = str(interaction.user)
    
    # Check if AI task - supports multiple prefixes for mobile convenience
    text_lower = text.lower().strip()
    is_ai_task = any(text_lower.startswith(p) for p in [
        "ai:", "ai：", "ai ",      # ai variants
        "kimi:", "kimi：", "kimi "  # kimi variants
    ])
    
    try:
        task_id = create_task("command", text)
        write_audit_log(actor, "/task", "success", f"Task #{task_id}: {text[:50]}")
        
        if is_ai_task:
            # AI tasks are executed asynchronously by Main Loop
            await interaction.response.send_message(
                f"🤖 Task #{task_id} queued for AI execution.\n"
                f"Use `/result {task_id}` to check result."
            )
        else:
            await interaction.response.send_message(f"Task #{task_id} recorded.")
            
    except Exception as e:
        write_audit_log(actor, "/task", "failed", str(e))
        await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)


# Phase 6: Controlled Self-Evolution Runtime

@bot.tree.command(name="evolve", description="Request AI evolution (Phase 6)")
@app_commands.describe(goal="What improvement should AI propose?")
async def evolve_command(interaction: discord.Interaction, goal: str):
    """Create evolution proposal.
    
    AI generates patch in isolated workspace.
    Never modifies running runtime.
    """
    await interaction.response.defer()
    
    try:
        # Create evolution task
        task_id = create_task("evolution_request", f"evolve: {goal}")
        
        # Create proposal (AI generates patch)
        proposal_path = create_evolution_proposal(task_id, goal)
        
        proposal_id = os.path.basename(proposal_path)
        
        await interaction.followup.send(
            f"Evolution request created.\n"
            f"Task: #{task_id}\n"
            f"Proposal: {proposal_id}\n"
            f"Status: proposed (awaiting validation)"
        )
        
    except Exception as e:
        await interaction.followup.send(
            f"Error creating evolution: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="approve", description="Approve evolution proposal")
@app_commands.describe(proposal_id="Proposal ID to approve")
async def approve_command(interaction: discord.Interaction, proposal_id: str):
    """Approve evolution proposal.
    
    Does NOT switch runtime - only marks as approved.
    Use /switch to deploy approved proposals.
    """
    try:
        # Find job by proposal path
        jobs = list_evolution_jobs(status="validated", limit=100)
        target_job = None
        
        for job in jobs:
            if proposal_id in job[2]:  # proposal_path contains proposal_id
                target_job = job
                break
        
        if not target_job:
            await interaction.response.send_message(
                f"No validated proposal found: {proposal_id}",
                ephemeral=True
            )
            return
        
        job_id = target_job[0]
        update_evolution_job_status(job_id, "approved")
        
        await interaction.response.send_message(
            f"Proposal {proposal_id} approved.\n"
            f"Use /switch to deploy when ready."
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"Error: {str(e)}",
            ephemeral=True
        )


@bot.tree.command(name="reject", description="Reject evolution proposal")
@app_commands.describe(proposal_id="Proposal ID to reject")
async def reject_command(interaction: discord.Interaction, proposal_id: str):
    """Reject evolution proposal."""
    try:
        # Find job by proposal path
        jobs = list_evolution_jobs(limit=100)
        target_job = None
        
        for job in jobs:
            if proposal_id in job[2]:  # proposal_path
                target_job = job
                break
        
        if not target_job:
            await interaction.response.send_message(
                f"No proposal found: {proposal_id}",
                ephemeral=True
            )
            return
        
        job_id = target_job[0]
        update_evolution_job_status(job_id, "rejected")
        
        await interaction.response.send_message(
            f"Proposal {proposal_id} rejected."
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"Error: {str(e)}",
            ephemeral=True
        )


def _parse_ai_result(result_text: str) -> dict:
    """Parse and unwrap AI result for display.
    
    Handles formats:
    - AI_{"actions": [...], "explanation": "...", ...}
    - Plain text (mock results)
    """
    import json
    
    # Remove AI_ prefix if present
    if result_text.startswith("AI_"):
        json_str = result_text[3:]
    elif result_text.startswith("Executed: "):
        # Mock result
        return {"type": "mock", "content": result_text}
    else:
        json_str = result_text
    
    # Try to parse as JSON Action Schema
    try:
        data = json.loads(json_str)
        if isinstance(data, dict) and "actions" in data:
            return {"type": "ai", "data": data}
        return {"type": "text", "content": result_text}
    except json.JSONDecodeError:
        return {"type": "text", "content": result_text}


@bot.tree.command(name="result", description="Query task execution result")
@app_commands.describe(task_id="Task ID to query")
async def result_command(interaction: discord.Interaction, task_id: str):
    """Query task result from database with friendly display."""
    from aegisos.db.sqlite_store import get_task
    
    try:
        task = get_task(int(task_id))
        if not task:
            await interaction.response.send_message(
                f"Task #{task_id} not found.",
                ephemeral=True
            )
            return
        
        task_id, task_type, status, payload, created_at, updated_at = task
        
        # Extract result from payload (after "RESULT: ")
        raw_result = "No result yet"
        if "\nRESULT: " in payload:
            raw_result = payload.split("\nRESULT: ", 1)[1]
        
        # Parse AI result
        parsed = _parse_ai_result(raw_result)
        
        # Build command display (original input)
        command_line = payload.split("\n")[0]
        if len(command_line) > 80:
            command_line = command_line[:77] + "..."
        
        # Status emoji
        status_emoji = "✅" if status == "completed" else ("🔄" if status == "running" else "⏳")
        
        # Format result based on type
        if parsed["type"] == "ai":
            data = parsed["data"]
            
            # Build actions summary
            actions_summary = []
            for action in data.get("actions", []):
                action_type = action.get("type", "unknown")
                if action_type == "edit_file":
                    actions_summary.append(f"📝 Edit {action.get('file', 'unknown')}")
                elif action_type == "create_file":
                    actions_summary.append(f"📄 Create {action.get('file', 'unknown')}")
                elif action_type == "update_memory":
                    actions_summary.append(f"💾 Memory: {action.get('key', 'unknown')}")
                elif action_type == "shell_command":
                    actions_summary.append(f"⚡ Shell: {action.get('command', 'unknown')[:30]}...")
                else:
                    actions_summary.append(f"🔧 {action_type}")
            
            if not actions_summary:
                actions_summary.append("(No actions)")
            
            # Risk level emoji
            risk = data.get("risk_level", "unknown")
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk, "⚪")
            
            # Build message
            message = (
                f"{status_emoji} **Task #{task_id}** {risk_emoji} `{risk}`\n"
                f"```\n{command_line}\n```\n"
                f"**Explanation:**\n{data.get('explanation', 'No explanation')}\n\n"
                f"**Actions ({len(data.get('actions', []))}):**\n"
            )
            for action in actions_summary:
                message += f"• {action}\n"
            
            # Add raw JSON in spoiler for debugging
            message += f"\n||📋 Raw: {raw_result[:200]}...||"
            
        elif parsed["type"] == "mock":
            message = (
                f"{status_emoji} **Task #{task_id}** (Mock)\n"
                f"```\n{command_line}\n```\n"
                f"Result: `{parsed['content']}`"
            )
        else:
            # Plain text
            display_result = raw_result[:1000] + "..." if len(raw_result) > 1000 else raw_result
            message = (
                f"{status_emoji} **Task #{task_id}**\n"
                f"```\n{command_line}\n```\n"
                f"Result:\n```\n{display_result}\n```"
            )
        
        await interaction.response.send_message(message, ephemeral=True)
        
    except ValueError:
        await interaction.response.send_message(
            "Invalid task ID. Please provide a number.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Error: {str(e)}",
            ephemeral=True
        )


def run():
    """Run Discord bot."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN environment variable not set")
        return
    bot.run(token)


if __name__ == "__main__":
    run()
