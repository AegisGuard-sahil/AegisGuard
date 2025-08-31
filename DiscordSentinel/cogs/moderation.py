import discord
from discord.ext import commands
import json
from datetime import datetime, timedelta
from utils.database import Database
from utils.permissions import has_permission, is_immune

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @discord.app_commands.command(name="kick", description="Kick a user from the server")
    @discord.app_commands.describe(
        user="The user to kick",
        reason="Reason for the kick"
    )
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Check if user is immune
        if is_immune(user):
            await interaction.response.send_message("❌ Cannot kick this user (immune role).", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild or not interaction.guild.me or not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message("❌ I don't have permission to kick members.", ephemeral=True)
            return
        
        # Check role hierarchy
        if (hasattr(user, 'top_role') and hasattr(interaction.user, 'top_role') and 
            user.top_role >= interaction.user.top_role and 
            interaction.guild and interaction.user.id != interaction.guild.owner_id):
            await interaction.response.send_message("❌ You cannot kick this user (role hierarchy).", ephemeral=True)
            return
        
        try:
            # Send DM to user before kicking
            try:
                embed = discord.Embed(
                    title="🦵 You have been kicked",
                    description=f"You were kicked from **{interaction.guild.name if interaction.guild else 'Unknown Server'}**",
                    color=0xe74c3c
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                await user.send(embed=embed)
            except:
                pass  # User has DMs disabled
            
            # Kick the user
            await user.kick(reason=f"Kicked by {interaction.user} | {reason}")
            
            # Log the action
            self.db.log_action("kick", interaction.user.id, user.id, reason)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ User Kicked",
                description=f"**{user}** has been kicked from the server.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="ban", description="Ban a user from the server")
    @discord.app_commands.describe(
        user="The user to ban",
        reason="Reason for the ban",
        delete_messages="Days of messages to delete (0-7)"
    )
    async def ban(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided", delete_messages: int = 0):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Validate delete_messages parameter
        if delete_messages < 0 or delete_messages > 7:
            await interaction.response.send_message("❌ Delete messages must be between 0 and 7 days.", ephemeral=True)
            return
        
        # Check if user is immune
        if is_immune(user):
            await interaction.response.send_message("❌ Cannot ban this user (immune role).", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild or not interaction.guild.me or not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
            return
        
        # Check role hierarchy
        if (hasattr(user, 'top_role') and hasattr(interaction.user, 'top_role') and 
            user.top_role >= interaction.user.top_role and 
            interaction.guild and interaction.user.id != interaction.guild.owner_id):
            await interaction.response.send_message("❌ You cannot ban this user (role hierarchy).", ephemeral=True)
            return
        
        try:
            # Send DM to user before banning
            try:
                embed = discord.Embed(
                    title="🔨 You have been banned",
                    description=f"You were banned from **{interaction.guild.name if interaction.guild else 'Unknown Server'}**",
                    color=0xe74c3c
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                await user.send(embed=embed)
            except:
                pass  # User has DMs disabled
            
            # Ban the user
            await user.ban(reason=f"Banned by {interaction.user} | {reason}", delete_message_days=delete_messages)
            
            # Log the action
            self.db.log_action("ban", interaction.user.id, user.id, reason)
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ User Banned",
                description=f"**{user}** has been banned from the server.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Messages Deleted", value=f"{delete_messages} days", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="mute", description="Mute a user")
    @discord.app_commands.describe(
        user="The user to mute",
        duration="Duration in minutes (default: 10)",
        reason="Reason for the mute"
    )
    async def mute(self, interaction: discord.Interaction, user: discord.Member, duration: int = 10, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Check if user is immune
        if is_immune(user):
            await interaction.response.send_message("❌ Cannot mute this user (immune role).", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild or not interaction.guild.me or not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ I don't have permission to timeout members.", ephemeral=True)
            return
        
        # Validate duration
        if duration <= 0 or duration > 40320:  # Max 28 days
            await interaction.response.send_message("❌ Duration must be between 1 minute and 28 days.", ephemeral=True)
            return
        
        try:
            # Calculate timeout until
            timeout_until = datetime.utcnow() + timedelta(minutes=duration)
            
            # Apply timeout
            await user.timeout(timeout_until, reason=f"Muted by {interaction.user} | {reason}")
            
            # Log the action
            self.db.log_action("mute", interaction.user.id, user.id, f"{reason} | Duration: {duration} minutes")
            
            # Send confirmation
            embed = discord.Embed(
                title="🔇 User Muted",
                description=f"**{user}** has been muted for {duration} minutes.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Duration", value=f"{duration} minutes", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to mute this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="unmute", description="Unmute a user")
    @discord.app_commands.describe(
        user="The user to unmute",
        reason="Reason for the unmute"
    )
    async def unmute(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Check if user is muted
        if not user.is_timed_out():
            await interaction.response.send_message("❌ This user is not muted.", ephemeral=True)
            return
        
        try:
            # Remove timeout
            await user.timeout(None, reason=f"Unmuted by {interaction.user} | {reason}")
            
            # Log the action
            self.db.log_action("unmute", interaction.user.id, user.id, reason)
            
            # Send confirmation
            embed = discord.Embed(
                title="🔊 User Unmuted",
                description=f"**{user}** has been unmuted.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unmute this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="warn", description="Warn a user")
    @discord.app_commands.describe(
        user="The user to warn",
        reason="Reason for the warning"
    )
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        # Check if user is immune
        if is_immune(user):
            await interaction.response.send_message("❌ Cannot warn this user (immune role).", ephemeral=True)
            return
        
        try:
            # Add warning to database
            warning_id = self.db.add_warning(user.id, interaction.user.id, reason)
            warnings_count = self.db.get_warning_count(user.id)
            
            # Send DM to user
            try:
                embed = discord.Embed(
                    title="⚠️ You have been warned",
                    description=f"You received a warning in **{interaction.guild.name}**",
                    color=0xf39c12
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Warning #", value=warnings_count, inline=False)
                embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
                if hasattr(user, 'send'):
                    await user.send(embed=embed)
            except:
                pass  # User has DMs disabled
            
            # Send confirmation
            embed = discord.Embed(
                title="⚠️ User Warned",
                description=f"**{user}** has been warned.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Warning #", value=warnings_count, inline=True)
            embed.add_field(name="Warning ID", value=warning_id, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            # Check if auto-ban should be triggered
            max_warnings = 3  # This could be loaded from config
            if warnings_count >= max_warnings:
                embed.add_field(
                    name="⚠️ Maximum Warnings Reached",
                    value=f"User has {warnings_count}/{max_warnings} warnings. Consider taking further action.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="warnings", description="View warnings for a user")
    @discord.app_commands.describe(user="The user to check warnings for")
    async def warnings(self, interaction: discord.Interaction, user: discord.Member):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return
        
        try:
            warnings = self.db.get_warnings(user.id)
            
            if not warnings:
                embed = discord.Embed(
                    title="✅ No Warnings",
                    description=f"**{user}** has no warnings.",
                    color=0x2ecc71
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title=f"⚠️ Warnings for {user}",
                description=f"Total warnings: {len(warnings)}",
                color=0xf39c12
            )
            
            for i, warning in enumerate(warnings[-5:], 1):  # Show last 5 warnings
                moderator = self.bot.get_user(warning['moderator_id'])
                moderator_name = moderator.name if moderator and hasattr(moderator, 'name') else "Unknown"
                
                embed.add_field(
                    name=f"Warning #{warning['id']}",
                    value=f"**Reason:** {warning['reason']}\n"
                          f"**Moderator:** {moderator_name}\n"
                          f"**Date:** {warning['timestamp'][:10]}",
                    inline=False
                )
            
            if len(warnings) > 5:
                embed.set_footer(text=f"Showing last 5 of {len(warnings)} warnings")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))
