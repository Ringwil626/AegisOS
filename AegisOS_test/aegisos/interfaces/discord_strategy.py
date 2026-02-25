"""Discord Strategy Commands - Phase6 Strategy Management.

Commands:
- /strategy list
- /strategy switch <proposal_id>
- /strategy rollback <version_id>
- /strategy status
"""
import discord
from discord import app_commands
from typing import Optional

import os
import sys
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.intelligence.strategy_manager import StrategyManager
from aegisos.intelligence.optimizer import ProposalManager, ProposalStatus


class StrategyCommands:
    """Discord strategy command handlers."""
    
    @staticmethod
    async def list_strategies(interaction: discord.Interaction):
        """List strategy versions."""
        await interaction.response.defer(thinking=True)
        
        try:
            history = StrategyManager.get_version_history(limit=10)
            
            if not history:
                await interaction.followup.send(
                    "No strategy versions found.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="📋 Strategy Versions",
                description="Version history and status",
                color=discord.Color.blue()
            )
            
            for v in history[:5]:
                status_emoji = {
                    'active': '🟢',
                    'shadow': '👥',
                    'retired': '⏹️'
                }.get(v['status'], '❓')
                
                value = f"{status_emoji} **{v['version_tag']}**\n"
                value += f"Status: {v['status']}\n"
                value += f"Created: {v['created_at'][:19] if isinstance(v['created_at'], str) else v['created_at']}"
                
                if v['proposal_id']:
                    value += f"\nFrom proposal: #{v['proposal_id']}"
                
                embed.add_field(
                    name=f"Version #{v['id']}",
                    value=value,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def switch_strategy(interaction: discord.Interaction, proposal_id: int):
        """Switch to a new strategy version."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Check if proposal is approved and has shadow data
            proposal = ProposalManager.get_proposal(proposal_id)
            
            if not proposal:
                await interaction.followup.send(
                    f"❌ Proposal #{proposal_id} not found",
                    ephemeral=True
                )
                return
            
            if proposal.status != ProposalStatus.SHADOW:
                await interaction.followup.send(
                    f"❌ Proposal #{proposal_id} is not ready for switch (status: {proposal.status.value})\n"
                    f"Must complete shadow validation first.",
                    ephemeral=True
                )
                return
            
            # Get version ID
            version_id = StrategyManager.get_version_by_proposal(proposal_id)
            if not version_id:
                await interaction.followup.send(
                    f"❌ No strategy version found for proposal #{proposal_id}",
                    ephemeral=True
                )
                return
            
            # Perform switch
            success = StrategyManager.switch_to_version(version_id)
            
            if success:
                # Update proposal status
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE proposals SET status = 'done' WHERE id = ?",
                    (proposal_id,)
                )
                conn.commit()
                conn.close()
                
                embed = discord.Embed(
                    title="🚀 Strategy Switched",
                    description=f"Successfully activated strategy from proposal #{proposal_id}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Version ID",
                    value=str(version_id),
                    inline=True
                )
                embed.add_field(
                    name="Rollback",
                    value=f"Use `/strategy rollback {version_id}` if issues occur",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to switch strategy",
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def rollback_strategy(interaction: discord.Interaction, version_id: int):
        """Rollback to a previous strategy version."""
        await interaction.response.defer(thinking=True)
        
        try:
            success = StrategyManager.rollback_to_version(version_id)
            
            if success:
                embed = discord.Embed(
                    title="↩️ Strategy Rollback",
                    description=f"Successfully rolled back to version #{version_id}",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to rollback to version #{version_id}",
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def strategy_status(interaction: discord.Interaction):
        """Show current strategy status."""
        await interaction.response.defer(thinking=True)
        
        try:
            active = StrategyManager.get_active_version()
            
            if not active:
                await interaction.followup.send(
                    "No active strategy found.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🎯 Current Strategy",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Version Tag",
                value=active.version_tag,
                inline=True
            )
            embed.add_field(
                name="Version ID",
                value=str(active.id),
                inline=True
            )
            
            # Show config
            config_lines = []
            for key, value in active.config_json.items():
                config_lines.append(f"{key}: {value}")
            
            embed.add_field(
                name="Configuration",
                value="\n".join(config_lines) or "Default",
                inline=False
            )
            
            if active.proposal_id:
                embed.add_field(
                    name="From Proposal",
                    value=f"#{active.proposal_id}",
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


# Command registration

def register_strategy_commands(tree: app_commands.CommandTree):
    """Register strategy commands."""
    
    @tree.command(name="strategy", description="Manage strategy versions")
    @app_commands.describe(
        action="Action to perform",
        proposal_id="Proposal ID (for switch)",
        version_id="Version ID (for rollback)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="switch", value="switch"),
        app_commands.Choice(name="rollback", value="rollback"),
        app_commands.Choice(name="status", value="status"),
    ])
    async def strategy_command(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        proposal_id: Optional[int] = None,
        version_id: Optional[int] = None
    ):
        if action.value == "list":
            await StrategyCommands.list_strategies(interaction)
        elif action.value == "switch":
            if not proposal_id:
                await interaction.response.send_message(
                    "Please provide a proposal_id",
                    ephemeral=True
                )
                return
            await StrategyCommands.switch_strategy(interaction, proposal_id)
        elif action.value == "rollback":
            if not version_id:
                await interaction.response.send_message(
                    "Please provide a version_id",
                    ephemeral=True
                )
                return
            await StrategyCommands.rollback_strategy(interaction, version_id)
        elif action.value == "status":
            await StrategyCommands.strategy_status(interaction)


# Need this import for the command handlers
import sqlite3
from aegisos.db.sqlite_store import DB_PATH
