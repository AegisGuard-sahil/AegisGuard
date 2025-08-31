import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from utils.database import Database
from utils.permissions import has_permission

class AntiRaidCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Anti-raid settings
        self.join_tracking = defaultdict(list)
        self.raid_threshold = 5  # users
        self.raid_window = 10  # seconds
        self.raid_protection_enabled = True
        
        # Lockdown status
        self.locked_guilds = set()
        
        # Auto-actions during raids
        self.raid_actions = {
            'kick_new_members': True,
            'lock_channels': True,
            'notify_staff': True
        }
    
    def is_raid_detected(self, guild_id: int) -> bool:
        """Check if a raid is currently happening"""
        now = datetime.utcnow()
        joins = self.join_tracking[guild_id]
        
        # Remove old joins
        joins[:] = [join_time for join_time in joins if (now - join_time).seconds < self.raid_window]
        
        return len(joins) >= self.raid_threshold
    
    async def handle_raid(self, guild: discord.Guild):
        """Handle detected raid"""
        if guild.id in self.locked_guilds:
            return  # Already handling
        
        self.locked_guilds.add(guild.id)
        
        try:
            # Notify staff
            if self.raid_actions['notify_staff']:
                await self.notify_staff(guild, "🚨 **RAID DETECTED** - Anti-raid measures activated!")
            
            # Lock channels
            if self.raid_actions['lock_channels']:
                await self.emergency_lockdown(guild)
            
            # Log the event
            self.db.log_action("raid_detected", None, None, f"Raid detected in {guild.name}")
            
        except Exception as e:
            print(f"Error handling raid: {e}")
    
    async def notify_staff(self, guild: discord.Guild, message: str):
        """Notify staff members about security events"""
        # Try to find staff channel
        staff_channels = [
            "staff", "mod-chat", "staff-chat", "moderators", 
            "admin", "admins", "security", "alerts"
        ]
        
        notification_channel = None
        for channel_name in staff_channels:
            channel = discord.utils.get(guild.channels, name=channel_name)
            if channel and isinstance(channel, discord.TextChannel):
                notification_channel = channel
                break
        
        if not notification_channel:
            # Fallback to first channel bot can send to
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    try:
                        if channel.permissions_for(guild.me).send_messages:
                            notification_channel = channel
                            break
                    except:
                        continue
        
        if notification_channel:
            embed = discord.Embed(
                title="🚨 Security Alert",
                description=message,
                color=0xe74c3c,
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name="Action Required",
                value="Review recent joins and take appropriate action",
                inline=False
            )
            
            try:
                await notification_channel.send(embed=embed)
            except:
                pass
    
    async def emergency_lockdown(self, guild: discord.Guild):
        """Lock down all channels during emergency"""
        locked_channels = 0
        
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                try:
                    # Create permission overwrite for @everyone
                    overwrite = discord.PermissionOverwrite()
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    
                    await channel.set_permissions(
                        guild.default_role,
                        overwrite=overwrite,
                        reason="Emergency lockdown - Raid protection"
                    )
                    locked_channels += 1
                except:
                    continue
        
        # Notify about lockdown
        await self.notify_staff(
            guild, 
            f"🔒 **EMERGENCY LOCKDOWN** - {locked_channels} channels locked due to raid detection"
        )
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Monitor member joins for raid detection"""
        if not self.raid_protection_enabled:
            return
        
        guild_id = member.guild.id
        now = datetime.utcnow()
        
        # Track join
        self.join_tracking[guild_id].append(now)
        
        # Check for raid
        if self.is_raid_detected(guild_id):
            await self.handle_raid(member.guild)
            
            # Kick new member if raid action is enabled
            if self.raid_actions['kick_new_members']:
                try:
                    await member.kick(reason="Anti-raid protection - Suspicious join pattern")
                    self.db.log_action(
                        "raid_kick", 
                        self.bot.user.id, 
                        member.id, 
                        "Kicked during raid protection"
                    )
                except:
                    pass
    
    @discord.app_commands.command(name="lockdown", description="Lock down the server in emergency")
    @discord.app_commands.describe(
        reason="Reason for lockdown"
    )
    async def lockdown_command(self, interaction: discord.Interaction, reason: str = "Emergency lockdown"):
        # Check permissions
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to use lockdown.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            await self.emergency_lockdown(interaction.guild)
            
            embed = discord.Embed(
                title="🔒 Server Lockdown Activated",
                description="All channels have been locked to prevent spam/raids.",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(name="Use", value="`/unlock` to restore normal permissions", inline=False)
            
            await interaction.followup.send(embed=embed)
            
            # Log action
            self.db.log_action("manual_lockdown", interaction.user.id, None, reason)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during lockdown: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="unlock", description="Remove lockdown and restore normal permissions")
    @discord.app_commands.describe(
        reason="Reason for unlocking"
    )
    async def unlock_command(self, interaction: discord.Interaction, reason: str = "Lockdown lifted"):
        # Check permissions
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to unlock.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            unlocked_channels = 0
            
            for channel in interaction.guild.channels:
                if isinstance(channel, discord.TextChannel):
                    try:
                        # Remove the lockdown overwrite
                        await channel.set_permissions(
                            interaction.guild.default_role,
                            overwrite=None,
                            reason="Lockdown lifted"
                        )
                        unlocked_channels += 1
                    except:
                        continue
            
            # Remove from locked guilds
            self.locked_guilds.discard(interaction.guild.id)
            
            embed = discord.Embed(
                title="🔓 Server Unlocked",
                description=f"Lockdown lifted. {unlocked_channels} channels restored to normal permissions.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await interaction.followup.send(embed=embed)
            
            # Log action
            self.db.log_action("unlock", interaction.user.id, None, reason)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during unlock: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="antiraid", description="Configure anti-raid protection")
    @discord.app_commands.describe(
        enabled="Enable or disable anti-raid protection",
        threshold="Number of joins to trigger protection (1-20)",
        window="Time window in seconds (5-60)"
    )
    async def antiraid_config(self, interaction: discord.Interaction, 
                            enabled: bool = None, 
                            threshold: int = None, 
                            window: int = None):
        
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to configure anti-raid.", ephemeral=True)
            return
        
        # Update settings if provided
        if enabled is not None:
            self.raid_protection_enabled = enabled
        
        if threshold is not None:
            if 1 <= threshold <= 20:
                self.raid_threshold = threshold
            else:
                await interaction.response.send_message("❌ Threshold must be between 1 and 20.", ephemeral=True)
                return
        
        if window is not None:
            if 5 <= window <= 60:
                self.raid_window = window
            else:
                await interaction.response.send_message("❌ Window must be between 5 and 60 seconds.", ephemeral=True)
                return
        
        # Show current configuration
        embed = discord.Embed(
            title="🛡️ Anti-Raid Configuration",
            color=0x3498db
        )
        
        status = "🟢 Enabled" if self.raid_protection_enabled else "🔴 Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Threshold", value=f"{self.raid_threshold} joins", inline=True)
        embed.add_field(name="Time Window", value=f"{self.raid_window} seconds", inline=True)
        
        actions_text = []
        for action, enabled_status in self.raid_actions.items():
            status_emoji = "✅" if enabled_status else "❌"
            action_name = action.replace('_', ' ').title()
            actions_text.append(f"{status_emoji} {action_name}")
        
        embed.add_field(
            name="Raid Actions",
            value="\n".join(actions_text),
            inline=False
        )
        
        embed.set_footer(text="Use the parameters to modify settings")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AntiRaidCog(bot))