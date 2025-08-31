import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from utils.database import Database
from utils.permissions import has_permission

class AntiNukeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Anti-nuke settings
        self.antinuke_enabled = True
        self.panic_mode = False
        self.panic_threshold = 3  # actions in 30 seconds
        self.panic_window = 30  # seconds
        
        # Action tracking
        self.action_tracking = defaultdict(list)
        self.suspicious_users = set()
        
        # Monitored actions
        self.monitored_actions = {
            'channel_delete': True,
            'channel_create': True,
            'role_delete': True,
            'role_create': True,
            'member_ban': True,
            'member_kick': True,
            'webhook_create': True,
            'webhook_delete': True
        }
        
        # Immune users (extra owners)
        self.immune_users = set()
    
    def is_suspicious_activity(self, user_id: int, action_type: str) -> bool:
        """Check if user's actions are suspicious"""
        if not self.antinuke_enabled:
            return False
        
        if user_id in self.immune_users:
            return False
        
        now = datetime.utcnow()
        key = f"{user_id}_{action_type}"
        
        # Clean old actions
        self.action_tracking[key] = [
            action_time for action_time in self.action_tracking[key]
            if (now - action_time).seconds < self.panic_window
        ]
        
        # Add current action
        self.action_tracking[key].append(now)
        
        # Check if threshold exceeded
        return len(self.action_tracking[key]) >= self.panic_threshold
    
    async def trigger_panic_mode(self, guild: discord.Guild, user: discord.Member, action_type: str):
        """Trigger panic mode and quarantine suspicious user"""
        if self.panic_mode:
            return  # Already in panic mode
        
        self.panic_mode = True
        self.suspicious_users.add(user.id)
        
        try:
            # Quarantine the suspicious user
            quarantine_cog = self.bot.get_cog('QuarantineCog')
            if quarantine_cog:
                await quarantine_cog.quarantine_user(
                    user, 
                    guild.me, 
                    f"ANTI-NUKE: Suspicious {action_type} activity detected"
                )
            
            # Remove dangerous permissions
            try:
                dangerous_perms = discord.Permissions.none()
                await user.edit(roles=[], reason="Anti-nuke panic mode")
            except:
                pass
            
            # Notify staff
            await self.notify_panic_mode(guild, user, action_type)
            
            # Log the event
            self.db.log_action(
                "antinuke_panic", 
                self.bot.user.id, 
                user.id, 
                f"Panic mode triggered by {action_type}"
            )
            
            # Auto-disable panic mode after 5 minutes
            await asyncio.sleep(300)
            self.panic_mode = False
            
        except Exception as e:
            print(f"Error in panic mode: {e}")
    
    async def notify_panic_mode(self, guild: discord.Guild, user: discord.Member, action_type: str):
        """Notify staff about panic mode activation"""
        # Find notification channel
        channels = ["staff", "mod-log", "security", "alerts", "admin"]
        notification_channel = None
        
        for channel_name in channels:
            channel = discord.utils.get(guild.channels, name=channel_name)
            if channel and isinstance(channel, discord.TextChannel):
                notification_channel = channel
                break
        
        if notification_channel:
            embed = discord.Embed(
                title="🚨 ANTI-NUKE PANIC MODE ACTIVATED",
                description="Suspicious administrative activity detected!",
                color=0xff0000,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="🎯 Suspicious User",
                value=f"{user.mention} ({user.name})\nID: {user.id}",
                inline=True
            )
            
            embed.add_field(
                name="⚠️ Detected Activity",
                value=f"Mass {action_type.replace('_', ' ')} actions",
                inline=True
            )
            
            embed.add_field(
                name="🛡️ Actions Taken",
                value="• User quarantined\n• Permissions revoked\n• Activity monitoring active",
                inline=False
            )
            
            embed.add_field(
                name="📋 Next Steps",
                value="1. Review recent audit log\n2. Check for damage\n3. Use `/antinuke disable` if false alarm\n4. Use `/backup restore` if needed",
                inline=False
            )
            
            try:
                await notification_channel.send("@here", embed=embed)
            except:
                pass
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        """Monitor channel deletions"""
        if not self.monitored_actions['channel_delete']:
            return
        
        # Get who deleted the channel from audit log
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
            if entry.target.id == channel.id:
                if self.is_suspicious_activity(entry.user.id, 'channel_delete'):
                    await self.trigger_panic_mode(channel.guild, entry.user, 'channel_delete')
                break
    
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Monitor channel creations"""
        if not self.monitored_actions['channel_create']:
            return
        
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
            if entry.target.id == channel.id:
                if self.is_suspicious_activity(entry.user.id, 'channel_create'):
                    await self.trigger_panic_mode(channel.guild, entry.user, 'channel_create')
                break
    
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        """Monitor role deletions"""
        if not self.monitored_actions['role_delete']:
            return
        
        async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
            if entry.target.id == role.id:
                if self.is_suspicious_activity(entry.user.id, 'role_delete'):
                    await self.trigger_panic_mode(role.guild, entry.user, 'role_delete')
                break
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Monitor member bans"""
        if not self.monitored_actions['member_ban']:
            return
        
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=1):
            if entry.target.id == user.id:
                if self.is_suspicious_activity(entry.user.id, 'member_ban'):
                    await self.trigger_panic_mode(guild, entry.user, 'member_ban')
                break
    
    @discord.app_commands.command(name="antinuke", description="Configure anti-nuke protection settings")
    @discord.app_commands.describe(
        action="What to configure",
        enabled="Enable or disable the feature"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="Enable/Disable Anti-Nuke", value="toggle"),
        discord.app_commands.Choice(name="Channel Protection", value="channels"),
        discord.app_commands.Choice(name="Role Protection", value="roles"),
        discord.app_commands.Choice(name="Member Protection", value="members"),
        discord.app_commands.Choice(name="View Status", value="status")
    ])
    async def antinuke_config(self, interaction: discord.Interaction, action: str, enabled: bool = None):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to configure anti-nuke.", ephemeral=True)
            return
        
        if action == "toggle" and enabled is not None:
            self.antinuke_enabled = enabled
            status = "✅ Enabled" if enabled else "❌ Disabled"
            
            embed = discord.Embed(
                title="🛡️ Anti-Nuke Protection",
                description=f"Anti-nuke protection is now **{status}**",
                color=0x2ecc71 if enabled else 0xe74c3c
            )
            
            await interaction.response.send_message(embed=embed)
            
        elif action == "channels" and enabled is not None:
            self.monitored_actions['channel_delete'] = enabled
            self.monitored_actions['channel_create'] = enabled
            
        elif action == "roles" and enabled is not None:
            self.monitored_actions['role_delete'] = enabled
            self.monitored_actions['role_create'] = enabled
            
        elif action == "members" and enabled is not None:
            self.monitored_actions['member_ban'] = enabled
            self.monitored_actions['member_kick'] = enabled
            
        elif action == "status":
            embed = discord.Embed(
                title="🛡️ Anti-Nuke Status",
                color=0x3498db
            )
            
            status = "🟢 Active" if self.antinuke_enabled else "🔴 Disabled"
            panic_status = "🚨 ACTIVE" if self.panic_mode else "✅ Normal"
            
            embed.add_field(name="Protection Status", value=status, inline=True)
            embed.add_field(name="Panic Mode", value=panic_status, inline=True)
            embed.add_field(name="Threshold", value=f"{self.panic_threshold} actions/{self.panic_window}s", inline=True)
            
            monitored = []
            for action_name, is_enabled in self.monitored_actions.items():
                status_emoji = "✅" if is_enabled else "❌"
                monitored.append(f"{status_emoji} {action_name.replace('_', ' ').title()}")
            
            embed.add_field(
                name="Monitored Actions",
                value="\n".join(monitored),
                inline=False
            )
            
            if self.suspicious_users:
                embed.add_field(
                    name="Flagged Users",
                    value=f"{len(self.suspicious_users)} users flagged",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="panic", description="Manually trigger or disable panic mode")
    @discord.app_commands.describe(
        action="Enable or disable panic mode",
        target="User to target (for enable only)"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="Enable", value="enable"),
        discord.app_commands.Choice(name="Disable", value="disable")
    ])
    async def panic_command(self, interaction: discord.Interaction, action: str, target: discord.Member = None):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to control panic mode.", ephemeral=True)
            return
        
        if action == "enable":
            if not target:
                await interaction.response.send_message("❌ You must specify a target user for panic mode.", ephemeral=True)
                return
            
            await interaction.response.defer()
            await self.trigger_panic_mode(interaction.guild, target, "manual_trigger")
            
            embed = discord.Embed(
                title="🚨 Panic Mode Activated",
                description=f"Panic mode manually triggered for {target.mention}",
                color=0xff0000
            )
            
            await interaction.followup.send(embed=embed)
            
        elif action == "disable":
            self.panic_mode = False
            
            embed = discord.Embed(
                title="✅ Panic Mode Disabled",
                description="Panic mode has been manually disabled.",
                color=0x2ecc71
            )
            
            await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="immune", description="Manage anti-nuke immunity (extra owners)")
    @discord.app_commands.describe(
        action="Add or remove immunity",
        user="User to grant/revoke immunity"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="Add Immunity", value="add"),
        discord.app_commands.Choice(name="Remove Immunity", value="remove"),
        discord.app_commands.Choice(name="List Immune", value="list")
    ])
    async def immune_command(self, interaction: discord.Interaction, action: str, user: discord.Member = None):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to manage immunity.", ephemeral=True)
            return
        
        if action == "add":
            if not user:
                await interaction.response.send_message("❌ You must specify a user to grant immunity.", ephemeral=True)
                return
            
            self.immune_users.add(user.id)
            
            embed = discord.Embed(
                title="🛡️ Immunity Granted",
                description=f"{user.mention} is now immune to anti-nuke actions.",
                color=0x2ecc71
            )
            
            await interaction.response.send_message(embed=embed)
            
        elif action == "remove":
            if not user:
                await interaction.response.send_message("❌ You must specify a user to revoke immunity.", ephemeral=True)
                return
            
            self.immune_users.discard(user.id)
            
            embed = discord.Embed(
                title="⚠️ Immunity Revoked",
                description=f"{user.mention} is no longer immune to anti-nuke actions.",
                color=0xf39c12
            )
            
            await interaction.response.send_message(embed=embed)
            
        elif action == "list":
            if not self.immune_users:
                embed = discord.Embed(
                    title="🛡️ Immune Users",
                    description="No users are currently immune.",
                    color=0x95a5a6
                )
            else:
                immune_list = []
                for user_id in self.immune_users:
                    user = self.bot.get_user(user_id)
                    if user:
                        immune_list.append(f"• {user.mention} ({user.name})")
                    else:
                        immune_list.append(f"• ID: {user_id}")
                
                embed = discord.Embed(
                    title="🛡️ Immune Users",
                    description="\n".join(immune_list[:10]),
                    color=0x3498db
                )
                
                if len(self.immune_users) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(self.immune_users)} immune users")
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AntiNukeCog(bot))