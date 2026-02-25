"""Discord Proposal Commands - Phase6 Governance Interface.

Provides Discord interface for:
- Listing proposals
- Inspecting proposal details
- Approving proposals
- Switching strategies

Read-only queries + approval actions only.
"""
import discord
from discord import app_commands
from typing import Optional

import os
import sys
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.intelligence.optimizer import ProposalManager, ProposalStatus
from aegisos.intelligence.policy import StrategyManager
from aegisos.intelligence.orchestrator import approve_proposal, switch_strategy_version


class ProposalCommands:
    """Discord proposal command handlers."""
    
    @staticmethod
    async def list_proposals(
        interaction: discord.Interaction,
        project: Optional[str] = None,
        status: Optional[str] = None
    ):
        """List optimization proposals."""
        await interaction.response.defer(thinking=True)
        
        project = project or "aegisos"
        
        try:
            status_enum = ProposalStatus(status) if status else None
        except ValueError:
            await interaction.followup.send(
                f"Invalid status: {status}. Use: pending, approved, rejected, shadow, active",
                ephemeral=True
            )
            return
        
        try:
            proposals = ProposalManager.list_proposals(
                project=project,
                status=status_enum,
                limit=10
            )
            
            if not proposals:
                await interaction.followup.send(
                    f"No {status or ''} proposals found for {project}",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"📋 Optimization Proposals - {project}",
                color=discord.Color.blue()
            )
            
            for p in proposals[:5]:  # Show top 5
                status_emoji = {
                    'pending': '⏳',
                    'approved': '✅',
                    'rejected': '❌',
                    'shadow': '👥',
                    'active': '🚀',
                    'retired': '⏹️'
                }.get(p.status.value, '❓')
                
                value = f"{status_emoji} **{p.type.value}** ({p.risk_level.value} risk)\n"
                value += f"Reason: {p.reason[:100]}{'...' if len(p.reason) > 100 else ''}\n"
                value += f"Expected: {p.expected_gain}"
                
                embed.add_field(
                    name=f"#{p.id} - {p.status.value.upper()}",
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
    async def inspect_proposal(
        interaction: discord.Interaction,
        proposal_id: int
    ):
        """Inspect proposal details."""
        await interaction.response.defer(thinking=True)
        
        try:
            proposal = ProposalManager.get_proposal(proposal_id)
            
            if not proposal:
                await interaction.followup.send(
                    f"Proposal #{proposal_id} not found",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"🔍 Proposal #{proposal_id}",
                color=discord.Color.gold()
            )
            
            embed.add_field(name="Type", value=proposal.type.value, inline=True)
            embed.add_field(name="Status", value=proposal.status.value, inline=True)
            embed.add_field(name="Risk", value=proposal.risk_level.value, inline=True)
            
            embed.add_field(name="Project", value=proposal.project, inline=True)
            embed.add_field(name="Created", value=f"<t:{proposal.created_at}:R>", inline=True)
            
            if proposal.approved_by:
                embed.add_field(name="Approved By", value=proposal.approved_by, inline=True)
            
            embed.add_field(
                name="Reason",
                value=proposal.reason,
                inline=False
            )
            
            embed.add_field(
                name="Proposed Action",
                value=proposal.action,
                inline=False
            )
            
            embed.add_field(
                name="Expected Gain",
                value=proposal.expected_gain,
                inline=False
            )
            
            # Add action hint based on status
            if proposal.status == ProposalStatus.PENDING:
                embed.add_field(
                    name="Next Step",
                    value=f"Approve with: `/proposals approve {proposal_id}`",
                    inline=False
                )
            elif proposal.status == ProposalStatus.APPROVED:
                embed.add_field(
                    name="Next Step",
                    value="Shadow execution in progress...",
                    inline=False
                )
            elif proposal.status == ProposalStatus.SHADOW:
                embed.add_field(
                    name="Next Step",
                    value=f"Switch with: `/switch strategy_version={proposal.id}`",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def approve_proposal(
        interaction: discord.Interaction,
        proposal_id: int
    ):
        """Approve a proposal."""
        await interaction.response.defer(thinking=True)
        
        # Check admin permission
        # TODO: Add admin check
        
        try:
            from aegisos.intelligence.orchestrator import OptimizationOrchestrator
            
            orchestrator = OptimizationOrchestrator()
            success = orchestrator.approve_and_shadow(
                proposal_id=proposal_id,
                approved_by=str(interaction.user)
            )
            
            if success:
                embed = discord.Embed(
                    title="✅ Proposal Approved",
                    description=f"Proposal #{proposal_id} approved and shadow execution started",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Next Step",
                    value=f"Monitor with `/proposals inspect {proposal_id}`",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to approve proposal #{proposal_id}",
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def switch_strategy(
        interaction: discord.Interaction,
        version_id: int
    ):
        """Switch to a new strategy version."""
        await interaction.response.defer(thinking=True)
        
        # Check admin permission
        # TODO: Add admin check
        
        try:
            success = switch_strategy_version(version_id)
            
            if success:
                embed = discord.Embed(
                    title="🚀 Strategy Switched",
                    description=f"Activated strategy version #{version_id}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Monitoring",
                    value="System monitoring for 60 minutes. Can rollback if issues detected.",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to switch to version #{version_id}. Check shadow validation.",
                    ephemeral=True
                )
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error: {str(e)}",
                ephemeral=True
            )


# Command registration

def register_proposal_commands(tree: app_commands.CommandTree):
    """Register proposal commands."""
    
    @tree.command(name="proposals", description="Manage optimization proposals")
    @app_commands.describe(
        action="Action to perform",
        proposal_id="Proposal ID (for inspect/approve)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="list", value="list"),
        app_commands.Choice(name="inspect", value="inspect"),
        app_commands.Choice(name="approve", value="approve"),
    ])
    async def proposals_command(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        proposal_id: Optional[int] = None
    ):
        if action.value == "list":
            await ProposalCommands.list_proposals(interaction)
        elif action.value == "inspect":
            if not proposal_id:
                await interaction.response.send_message(
                    "Please provide a proposal_id",
                    ephemeral=True
                )
                return
            await ProposalCommands.inspect_proposal(interaction, proposal_id)
        elif action.value == "approve":
            if not proposal_id:
                await interaction.response.send_message(
                    "Please provide a proposal_id",
                    ephemeral=True
                )
                return
            await ProposalCommands.approve_proposal(interaction, proposal_id)
    
    @tree.command(name="switch", description="Switch to a new strategy version")
    @app_commands.describe(version_id="Strategy version to activate")
    async def switch_command(
        interaction: discord.Interaction,
        version_id: int
    ):
        await ProposalCommands.switch_strategy(interaction, version_id)
