"""
Enhanced Discord Bot for AegisOS
Features:
- Natural language command parsing
- Interactive buttons for common operations
- Rich embeds with color-coded status
- Thread-based task logs
- Permission-based access control
"""

import discord
from discord import app_commands, ui
from discord.ext import commands
import os
import sys
import re

_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.sqlite_store import (
    get_system_state, create_task, get_last_heartbeat,
    write_audit_log, get_task
)
from aegisos.core import supervisor

intents = discord.Intents.default()
intents.message_content = True  # For natural language parsing
bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command("help")

# Permission check
ADMIN_USERS = []  # Loaded from config

def load_config():
    """Load admin users from config."""
    global ADMIN_USERS
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            for line in f:
                if 'admin_users:' in line:
                    break
                if line.strip().startswith('-'):
                    user_id = line.strip().strip('-').strip().strip('"')
                    ADMIN_USERS.append(user_id)
    except:
        pass

def is_admin(user_id: str) -> bool:
    """Check if user has admin permissions."""
    return str(user_id) in ADMIN_USERS

# Color scheme for embeds
COLORS = {
    'success': discord.Color.green(),
    'warning': discord.Color.yellow(),
    'error': discord.Color.red(),
    'info': discord.Color.blue(),
    'running': discord.Color.orange(),
}

# ==================== UI Components ====================

class ControlButtons(ui.View):
    """Quick action buttons for common operations."""
    
    def __init__(self, user_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
    
    @ui.button(label="🟢 Wake", style=discord.ButtonStyle.green, custom_id="wake")
    async def wake_button(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(self.user_id):
            await interaction.response.send_message("⛔ Admin only", ephemeral=True)
            return
        
        if supervisor.is_running():
            await interaction.response.send_message("Already running!", ephemeral=True)
            return
        
        supervisor.start()
        await interaction.response.send_message("🟢 Supervisor started!")
    
    @ui.button(label="🔴 Stop", style=discord.ButtonStyle.red, custom_id="stop")
    async def stop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not is_admin(self.user_id):
            await interaction.response.send_message("⛔ Admin only", ephemeral=True)
            return
        
        if not supervisor.is_running():
            await interaction.response.send_message("Not running!", ephemeral=True)
            return
        
        supervisor.stop()
        await interaction.response.send_message("🔴 Supervisor stopped!")
    
    @ui.button(label="📊 Status", style=discord.ButtonStyle.blurple, custom_id="status")
    async def status_button(self, interaction: discord.Interaction, button: ui.Button):
        await show_status_embed(interaction)

class ConfirmView(ui.View):
    """Confirmation dialog for dangerous operations."""
    
    def __init__(self, action: str):
        super().__init__(timeout=30)
        self.action = action
        self.confirmed = False
    
    @ui.button(label="✅ Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        self.confirmed = True
        await interaction.response.send_message(f"Confirmed: {self.action}")
        self.stop()
    
    @ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Cancelled.")
        self.stop()

# ==================== Embeds ====================

def create_system_embed() -> discord.Embed:
    """Create system status embed."""
    system_status = get_system_state("status") or "unknown"
    runtime_version = get_system_state("runtime_version") or "unknown"
    supervisor_running = supervisor.is_running()
    
    # Color based on status
    if supervisor_running and system_status == "running":
        color = COLORS['success']
        status_emoji = "🟢"
    elif supervisor_running:
        color = COLORS['warning']
        status_emoji = "🟡"
    else:
        color = COLORS['error']
        status_emoji = "🔴"
    
    embed = discord.Embed(
        title=f"{status_emoji} AegisOS System Status",
        color=color,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="System",
        value=system_status.upper(),
        inline=True
    )
    embed.add_field(
        name="Runtime",
        value=runtime_version,
        inline=True
    )
    embed.add_field(
        name="Supervisor",
        value="Running ✅" if supervisor_running else "Stopped ❌",
        inline=True
    )
    
    # Heartbeat
    hb = get_last_heartbeat("supervisor")
    if hb:
        embed.add_field(
            name="Last Heartbeat",
            value=f"{hb['message']} (<t:{int(hb['timestamp'])}:R>)",
            inline=False
        )
    
    embed.set_footer(text="Use buttons below for quick actions")
    return embed

def create_task_embed(task_id: int, status: str, project: str = "default") -> discord.Embed:
    """Create task status embed."""
    status_colors = {
        "pending": COLORS['warning'],
        "running": COLORS['running'],
        "completed": COLORS['success'],
        "failed": COLORS['error'],
    }
    
    status_emojis = {
        "pending": "⏳",
        "running": "🔄",
        "completed": "✅",
        "failed": "❌",
    }
    
    embed = discord.Embed(
        title=f"{status_emojis.get(status, '❓')} Task #{task_id}",
        color=status_colors.get(status, COLORS['info']),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(name="Status", value=status.upper(), inline=True)
    embed.add_field(name="Project", value=project, inline=True)
    
    return embed

# ==================== Event Handlers ====================

@bot.event
async def on_ready():
    """Sync slash commands on ready."""
    print(f"Discord bot logged in as {bot.user}")
    load_config()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_message(message: discord.Message):
    """Handle natural language commands."""
    if message.author.bot:
        return
    
    # Only process in command channel
    if not is_command_channel(message.channel.id):
        return
    
    content = message.content.lower().strip()
    
    # Natural language parsing
    if any(content.startswith(x) for x in ["ai", "kimi", "code", "task"]):
        # Task creation
        await handle_natural_task(message)
        return
    
    if re.search(r"\b(status|state|how are you)\b", content):
        await message.reply(embed=create_system_embed(), view=ControlButtons(str(message.author.id)))
        return
    
    if re.search(r"\b(start|wake|begin|run)\b", content):
        if is_admin(str(message.author.id)):
            if supervisor.is_running():
                await message.reply("Already running! ✅")
            else:
                supervisor.start()
                await message.reply("🟢 Supervisor started!")
        else:
            await message.reply("⛔ Admin only", delete_after=5)
        return
    
    if re.search(r"\b(stop|halt|end|shutdown)\b", content):
        if is_admin(str(message.author.id)):
            if not supervisor.is_running():
                await message.reply("Already stopped! ❌")
            else:
                supervisor.stop()
                await message.reply("🔴 Supervisor stopped!")
        else:
            await message.reply("⛔ Admin only", delete_after=5)
        return

# ==================== Slash Commands ====================

@bot.tree.command(name="status", description="Get AegisOS system status")
async def status_command(interaction: discord.Interaction):
    """Display system status with embed and buttons."""
    await show_status_embed(interaction)

async def show_status_embed(interaction: discord.Interaction):
    """Show status embed with control buttons."""
    embed = create_system_embed()
    view = ControlButtons(str(interaction.user.id))
    
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="wake", description="Start AegisOS supervisor (Admin only)")
async def wake_command(interaction: discord.Interaction):
    """Start supervisor with admin check."""
    if not is_admin(str(interaction.user.id)):
        await interaction.response.send_message("⛔ This command requires admin privileges.", ephemeral=True)
        write_audit_log(str(interaction.user), "/wake", "rejected", "Not admin")
        return
    
    if supervisor.is_running():
        await interaction.response.send_message("✅ Supervisor is already running!", ephemeral=True)
        return
    
    supervisor.start()
    write_audit_log(str(interaction.user), "/wake", "success", "Supervisor started")
    
    embed = discord.Embed(
        title="🟢 Supervisor Started",
        description="AegisOS is now running and ready for tasks.",
        color=COLORS['success']
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Stop AegisOS supervisor (Admin only)")
async def stop_command(interaction: discord.Interaction):
    """Stop supervisor with admin check and confirmation."""
    if not is_admin(str(interaction.user.id)):
        await interaction.response.send_message("⛔ This command requires admin privileges.", ephemeral=True)
        return
    
    if not supervisor.is_running():
        await interaction.response.send_message("❌ Supervisor is not running.", ephemeral=True)
        return
    
    # Confirmation for dangerous operation
    view = ConfirmView("Stop Supervisor")
    await interaction.response.send_message(
        "⚠️ Are you sure you want to stop the supervisor?",
        view=view,
        ephemeral=True
    )
    
    await view.wait()
    
    if view.confirmed:
        supervisor.stop()
        write_audit_log(str(interaction.user), "/stop", "success", "Supervisor stopped")
        
        embed = discord.Embed(
            title="🔴 Supervisor Stopped",
            description="AegisOS has been stopped.",
            color=COLORS['error']
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="task", description="Create a new task")
@app_commands.describe(
    type="Task type",
    text="Task description",
    project="Target project"
)
@app_commands.choices(type=[
    app_commands.Choice(name="🖥️ Command", value="command"),
    app_commands.Choice(name="🤖 AI", value="ai"),
    app_commands.Choice(name="💻 Code", value="code"),
])
async def task_command(
    interaction: discord.Interaction,
    type: app_commands.Choice[str],
    text: str,
    project: str = "default"
):
    """Create task with confirmation and thread."""
    await interaction.response.defer(thinking=True)
    
    try:
        task_id = create_task(type.value, text, project=project)
        write_audit_log(
            str(interaction.user),
            f"/task {type.value}",
            "success",
            f"Task #{task_id} created"
        )
        
        # Create embed
        embed = discord.Embed(
            title=f"📋 Task Created",
            description=f"Task #{task_id} queued for execution",
            color=COLORS['info']
        )
        embed.add_field(name="Type", value=type.value, inline=True)
        embed.add_field(name="Project", value=project, inline=True)
        embed.add_field(name="Status", value="PENDING", inline=True)
        embed.add_field(name="Command", value=f"```{text[:100]}```", inline=False)
        
        # Send initial message
        msg = await interaction.followup.send(embed=embed)
        
        # Create thread for task logs
        try:
            thread = await msg.create_thread(
                name=f"Task #{task_id} Logs",
                auto_archive_duration=60  # Archive after 1 hour of inactivity
            )
            await thread.send("📊 Task progress will be logged here...")
        except:
            pass  # Threads may not be supported
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error creating task: {e}", ephemeral=True)

# ==================== Helper Functions ====================

async def handle_natural_task(message: discord.Message):
    """Handle natural language task creation."""
    content = message.content
    
    # Detect type from prefix
    type_map = {
        "code:": "code",
        "code ": "code",
        "ai:": "ai",
        "ai ": "ai",
    }
    
    task_type = "ai"  # Default
    for prefix, t in type_map.items():
        if content.lower().startswith(prefix):
            task_type = t
            content = content[len(prefix):].strip()
            break
    
    try:
        task_id = create_task(task_type, content)
        
        embed = discord.Embed(
            title="📝 Task Queued",
            description=f"Natural language task accepted",
            color=COLORS['info']
        )
        embed.add_field(name="Task ID", value=f"#{task_id}", inline=True)
        embed.add_field(name="Type", value=task_type, inline=True)
        embed.add_field(name="Preview", value=f"```{content[:100]}```", inline=False)
        
        await message.reply(embed=embed)
        
    except Exception as e:
        await message.reply(f"❌ Failed to create task: {e}")

def is_command_channel(channel_id: int) -> bool:
    """Check if channel is allowed for commands."""
    allowed = []
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            in_command = False
            for line in f:
                if 'command_channel:' in line:
                    in_command = True
                elif in_command and line.strip().startswith('-'):
                    cid = line.strip().strip('-').strip().strip('"')
                    allowed.append(cid)
                elif in_command and not line.strip().startswith(''):
                    break
    except:
        pass
    
    return str(channel_id) in allowed if allowed else True

# ==================== Entry Point ====================

def run():
    """Run the enhanced Discord bot."""
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("Error: DISCORD_TOKEN not set")
        return
    
    load_config()
    bot.run(token)

if __name__ == "__main__":
    run()
