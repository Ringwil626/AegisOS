"""Discord Usage Commands - Phase5 AI Usage Accounting.

Provides Discord interface for querying AI usage and budgets.
Read-only - no modification of budgets through Discord.

Commands:
- /usage today [project]
- /usage by_project
- /budget status [project]
"""
import discord
from discord import app_commands
from typing import Optional

import os
import sys
_current_dir = os.path.dirname(__file__)
_project_root = os.path.dirname(os.path.dirname(_current_dir))
sys.path.insert(0, _project_root)

from aegisos.db.usage_ledger import UsageLedger
from aegisos.ai.pricing import format_cost


class UsageCommands:
    """Discord usage command handlers."""
    
    @staticmethod
    async def usage_today(
        interaction: discord.Interaction,
        project: Optional[str] = None
    ):
        """Show today's usage for a project."""
        await interaction.response.defer(thinking=True)
        
        project = project or "aegisos"
        
        try:
            # Get usage
            usage = UsageLedger.get_project_usage_today(project)
            budget = UsageLedger.get_budget_config(project)
            
            # Build embed
            embed = discord.Embed(
                title=f"📊 Usage Report - {project}",
                description="Today's AI resource consumption",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Tasks",
                value=str(usage["task_count"]),
                inline=True
            )
            
            embed.add_field(
                name="Tokens",
                value=f"{usage['total_tokens']:,}",
                inline=True
            )
            
            embed.add_field(
                name="Cost",
                value=format_cost(usage["total_cost"]),
                inline=True
            )
            
            embed.add_field(
                name="Avg Latency",
                value=f"{usage['avg_latency_ms']:.1f}ms",
                inline=True
            )
            
            # Budget status
            if budget.daily_cost_limit:
                remaining = budget.daily_cost_limit - usage["total_cost"]
                percentage = (usage["total_cost"] / budget.daily_cost_limit) * 100
                
                status_color = "🟢"
                if percentage > 80:
                    status_color = "🟡"
                if percentage > 95:
                    status_color = "🔴"
                
                embed.add_field(
                    name="Budget",
                    value=f"{status_color} {format_cost(usage['total_cost'])} / {format_cost(budget.daily_cost_limit)} ({percentage:.1f}%)",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error fetching usage: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def usage_by_project(
        interaction: discord.Interaction
    ):
        """Show usage breakdown by project."""
        await interaction.response.defer(thinking=True)
        
        try:
            # Get all projects usage
            projects = UsageLedger.get_all_projects_usage_today()
            
            if not projects:
                await interaction.followup.send(
                    "No usage data available for today.",
                    ephemeral=True
                )
                return
            
            # Build embed
            embed = discord.Embed(
                title="📊 Usage by Project",
                description="Today's AI resource consumption across all projects",
                color=discord.Color.blue()
            )
            
            total_tasks = sum(p["task_count"] for p in projects)
            total_tokens = sum(p["total_tokens"] for p in projects)
            total_cost = sum(p["total_cost"] for p in projects)
            
            embed.add_field(
                name="Total",
                value=f"Tasks: {total_tasks}\nTokens: {total_tokens:,}\nCost: {format_cost(total_cost)}",
                inline=False
            )
            
            for proj in projects[:5]:  # Top 5 projects
                embed.add_field(
                    name=proj["project"],
                    value=(f"Tasks: {proj['task_count']}\n"
                           f"Tokens: {proj['total_tokens']:,}\n"
                           f"Cost: {format_cost(proj['total_cost'])}\n"
                           f"Avg: {proj['avg_latency_ms']:.0f}ms"),
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error fetching usage: {str(e)}",
                ephemeral=True
            )
    
    @staticmethod
    async def budget_status(
        interaction: discord.Interaction,
        project: Optional[str] = None
    ):
        """Show budget status for a project."""
        await interaction.response.defer(thinking=True)
        
        project = project or "aegisos"
        
        try:
            budget = UsageLedger.get_budget_config(project)
            usage = UsageLedger.get_project_usage_today(project)
            
            embed = discord.Embed(
                title=f"💰 Budget Status - {project}",
                color=discord.Color.gold()
            )
            
            # Token budget
            if budget.daily_token_limit:
                token_pct = (usage["total_tokens"] / budget.daily_token_limit) * 100
                token_bar = "█" * int(token_pct / 10) + "░" * (10 - int(token_pct / 10))
                
                embed.add_field(
                    name="Token Budget",
                    value=(f"{token_bar}\n"
                           f"{usage['total_tokens']:,} / {budget.daily_token_limit:,}\n"
                           f"({token_pct:.1f}%)"),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Token Budget",
                    value="No limit set",
                    inline=False
                )
            
            # Cost budget
            if budget.daily_cost_limit:
                cost_pct = (usage["total_cost"] / budget.daily_cost_limit) * 100
                cost_bar = "█" * int(cost_pct / 10) + "░" * (10 - int(cost_pct / 10))
                
                embed.add_field(
                    name="Cost Budget",
                    value=(f"{cost_bar}\n"
                           f"{format_cost(usage['total_cost'])} / {format_cost(budget.daily_cost_limit)}\n"
                           f"({cost_pct:.1f}%)"),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Cost Budget",
                    value="No limit set",
                    inline=False
                )
            
            # Rate limit
            embed.add_field(
                name="Rate Limit",
                value=f"{budget.max_tasks_per_minute} tasks/minute",
                inline=True
            )
            
            # Hard stop
            embed.add_field(
                name="Hard Stop",
                value="✅ Enabled" if budget.hard_stop else "⚠️ Disabled",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error fetching budget: {str(e)}",
                ephemeral=True
            )


# Command registration helpers

def register_usage_commands(tree: app_commands.CommandTree):
    """Register usage commands to command tree."""
    
    @tree.command(name="usage", description="Query AI usage statistics")
    @app_commands.describe(
        project="Project name (default: aegisos)",
        view="Usage view type"
    )
    @app_commands.choices(view=[
        app_commands.Choice(name="today", value="today"),
        app_commands.Choice(name="by_project", value="by_project"),
    ])
    async def usage_command(
        interaction: discord.Interaction,
        view: app_commands.Choice[str],
        project: Optional[str] = None
    ):
        if view.value == "today":
            await UsageCommands.usage_today(interaction, project)
        elif view.value == "by_project":
            await UsageCommands.usage_by_project(interaction)
    
    @tree.command(name="budget", description="Check budget status")
    @app_commands.describe(project="Project name (default: aegisos)")
    async def budget_command(
        interaction: discord.Interaction,
        project: Optional[str] = None
    ):
        await UsageCommands.budget_status(interaction, project)
