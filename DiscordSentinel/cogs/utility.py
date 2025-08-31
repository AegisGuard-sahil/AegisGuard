import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from utils.database import Database
from utils.permissions import has_permission

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Active slowmodes
        self.active_slowmodes = {}
    
    @discord.app_commands.command(name="slowmode", description="Set channel slowmode with optional duration")
    @discord.app_commands.describe(
        channel="Channel to apply slowmode to",
        seconds="Slowmode delay in seconds (0-21600)",
        duration="Duration in minutes (0 = permanent)"
    )
    async def slowmode_command(self, interaction: discord.Interaction, 
                             channel: discord.TextChannel = None, 
                             seconds: int = 0, 
                             duration: int = 0):
        
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to manage slowmode.", ephemeral=True)
            return
        
        target_channel = channel or interaction.channel
        
        # Validate seconds
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
            return
        
        try:
            # Apply slowmode
            await target_channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode set by {interaction.user}"
            )
            
            # Log action
            self.db.log_action(
                "slowmode", 
                interaction.user.id, 
                None, 
                f"Slowmode set to {seconds}s in #{target_channel.name}"
            )
            
            if seconds == 0:
                embed = discord.Embed(
                    title="🐌 Slowmode Disabled",
                    description=f"Slowmode has been disabled in {target_channel.mention}",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="🐌 Slowmode Enabled",
                    description=f"Slowmode set to **{seconds} seconds** in {target_channel.mention}",
                    color=0x3498db
                )
                
                if duration > 0:
                    embed.add_field(
                        name="⏰ Duration",
                        value=f"Will be disabled in {duration} minutes",
                        inline=False
                    )
                    
                    # Schedule removal
                    self.active_slowmodes[target_channel.id] = {
                        'end_time': datetime.utcnow() + timedelta(minutes=duration),
                        'original_delay': target_channel.slowmode_delay
                    }
                    
                    # Create task to remove slowmode
                    asyncio.create_task(self.remove_slowmode_after_duration(target_channel, duration))
            
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Channel", value=target_channel.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    async def remove_slowmode_after_duration(self, channel: discord.TextChannel, duration: int):
        """Remove slowmode after specified duration"""
        await asyncio.sleep(duration * 60)  # Convert minutes to seconds
        
        try:
            await channel.edit(slowmode_delay=0, reason="Temporary slowmode expired")
            
            # Remove from tracking
            self.active_slowmodes.pop(channel.id, None)
            
            # Send notification
            embed = discord.Embed(
                title="🐌 Slowmode Expired",
                description=f"Temporary slowmode has been removed from {channel.mention}",
                color=0x2ecc71
            )
            
            await channel.send(embed=embed, delete_after=10)
            
        except discord.NotFound:
            # Channel was deleted
            self.active_slowmodes.pop(channel.id, None)
        except discord.Forbidden:
            # Lost permissions
            pass
        except Exception as e:
            print(f"Error removing slowmode: {e}")
    
    @discord.app_commands.command(name="lock", description="Lock a channel to prevent messages")
    @discord.app_commands.describe(
        channel="Channel to lock",
        duration="Duration in minutes (0 = permanent)",
        reason="Reason for locking"
    )
    async def lock_command(self, interaction: discord.Interaction,
                          channel: discord.TextChannel = None,
                          duration: int = 0,
                          reason: str = "No reason provided"):
        
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to lock channels.", ephemeral=True)
            return
        
        target_channel = channel or interaction.channel
        
        try:
            # Create overwrite to deny send_messages
            overwrite = discord.PermissionOverwrite()
            overwrite.send_messages = False
            overwrite.add_reactions = False
            
            await target_channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"Channel locked by {interaction.user} | {reason}"
            )
            
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description=f"{target_channel.mention} has been locked.",
                color=0xe74c3c
            )
            
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if duration > 0:
                embed.add_field(
                    name="⏰ Duration",
                    value=f"Will be unlocked in {duration} minutes",
                    inline=True
                )
                
                # Schedule unlock
                asyncio.create_task(self.unlock_after_duration(target_channel, duration, interaction.user))
            
            await interaction.response.send_message(embed=embed)
            
            # Log action
            self.db.log_action(
                "lock_channel",
                interaction.user.id,
                None,
                f"Locked #{target_channel.name} | {reason}"
            )
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="unlock_channel", description="Unlock a channel to allow messages")
    @discord.app_commands.describe(
        channel="Channel to unlock",
        reason="Reason for unlocking"
    )
    async def unlock_command(self, interaction: discord.Interaction,
                           channel: discord.TextChannel = None,
                           reason: str = "No reason provided"):
        
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to unlock channels.", ephemeral=True)
            return
        
        target_channel = channel or interaction.channel
        
        try:
            # Remove the lockdown overwrite
            await target_channel.set_permissions(
                interaction.guild.default_role,
                overwrite=None,
                reason=f"Channel unlocked by {interaction.user} | {reason}"
            )
            
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description=f"{target_channel.mention} has been unlocked.",
                color=0x2ecc71
            )
            
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Log action
            self.db.log_action(
                "unlock_channel",
                interaction.user.id,
                None,
                f"Unlocked #{target_channel.name} | {reason}"
            )
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    async def unlock_after_duration(self, channel: discord.TextChannel, duration: int, moderator: discord.Member):
        """Unlock channel after specified duration"""
        await asyncio.sleep(duration * 60)  # Convert minutes to seconds
        
        try:
            await channel.set_permissions(
                channel.guild.default_role,
                overwrite=None,
                reason="Temporary lock expired"
            )
            
            embed = discord.Embed(
                title="🔓 Lock Expired",
                description=f"Temporary lock has been removed from {channel.mention}",
                color=0x2ecc71
            )
            
            await channel.send(embed=embed, delete_after=10)
            
            # Log action
            self.db.log_action(
                "auto_unlock",
                None,
                None,
                f"Temporary lock expired in #{channel.name}"
            )
            
        except discord.NotFound:
            # Channel was deleted
            pass
        except discord.Forbidden:
            # Lost permissions
            pass
        except Exception as e:
            print(f"Error auto-unlocking channel: {e}")
    
    @discord.app_commands.command(name="cases", description="View moderation cases for a user")
    @discord.app_commands.describe(
        user="User to view cases for",
        limit="Number of cases to show (max 20)"
    )
    async def cases_command(self, interaction: discord.Interaction, user: discord.Member, limit: int = 10):
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to view cases.", ephemeral=True)
            return
        
        if limit > 20:
            limit = 20
        elif limit < 1:
            limit = 1
        
        # Get user's moderation history
        warnings = self.db.get_warnings(user.id)
        logs = self.db.get_recent_logs(50, user.id)  # Get more logs to filter
        
        # Combine and sort by timestamp
        all_cases = []
        
        # Add warnings
        for warning in warnings:
            all_cases.append({
                'type': 'Warning',
                'id': warning['id'],
                'reason': warning['reason'],
                'moderator_id': warning['moderator_id'],
                'timestamp': warning['timestamp'],
                'emoji': '⚠️'
            })
        
        # Add other moderation actions
        mod_actions = ['ban', 'kick', 'mute', 'quarantine', 'timeout']
        for log in logs:
            if log['action'] in mod_actions:
                all_cases.append({
                    'type': log['action'].title(),
                    'id': None,
                    'reason': log['reason'],
                    'moderator_id': log['moderator_id'],
                    'timestamp': log['timestamp'],
                    'emoji': '🔨'
                })
        
        # Sort by timestamp (newest first)
        all_cases.sort(key=lambda x: x['timestamp'], reverse=True)
        
        if not all_cases:
            embed = discord.Embed(
                title="📋 No Cases Found",
                description=f"**{user}** has no moderation history.",
                color=0x2ecc71
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Show cases
        embed = discord.Embed(
            title=f"📋 Moderation Cases for {user}",
            description=f"Showing {min(len(all_cases), limit)} of {len(all_cases)} cases",
            color=0x3498db
        )
        
        for i, case in enumerate(all_cases[:limit], 1):
            moderator = self.bot.get_user(case['moderator_id']) if case['moderator_id'] else None
            moderator_name = moderator.name if moderator else "Unknown"
            
            case_id = f"#{case['id']}" if case['id'] else f"Case {i}"
            timestamp = case['timestamp'][:10]  # Just the date
            
            embed.add_field(
                name=f"{case['emoji']} {case['type']} {case_id}",
                value=f"**Reason:** {case['reason'][:100]}{'...' if len(case['reason']) > 100 else ''}\n"
                      f"**Moderator:** {moderator_name}\n"
                      f"**Date:** {timestamp}",
                inline=False
            )
        
        if len(all_cases) > limit:
            embed.set_footer(text=f"Use /cases user:{user.name} limit:{limit + 10} to see more")
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="setup", description="Quick setup wizard for server security")
    async def setup_command(self, interaction: discord.Interaction):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to run setup.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🛠️ Server Security Setup",
            description="Welcome to the security setup wizard! This will configure essential security features.",
            color=0x3498db
        )
        
        embed.add_field(
            name="📋 What will be configured:",
            value="• Anti-raid protection\n"
                  "• Anti-nuke monitoring\n"
                  "• Auto-moderation filters\n"
                  "• Quarantine system\n"
                  "• Verification system\n"
                  "• Backup creation",
            inline=False
        )
        
        embed.add_field(
            name="⏱️ Estimated Time",
            value="2-3 minutes",
            inline=True
        )
        
        embed.add_field(
            name="🔧 Requirements",
            value="Bot needs Administrator permissions",
            inline=True
        )
        
        view = SetupView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class SetupView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=300)
        self.cog = cog
    
    @discord.ui.button(label="Start Setup", style=discord.ButtonStyle.green, emoji="🚀")
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        guild = interaction.guild
        results = {
            'antinuke': False,
            'antiraid': False,
            'verification': False,
            'backup': False,
            'quarantine': False
        }
        
        embed = discord.Embed(
            title="🔄 Setting up security features...",
            description="Please wait while we configure your server.",
            color=0xf39c12
        )
        
        await interaction.edit_original_response(embed=embed, view=None)
        
        try:
            # Configure anti-nuke
            antinuke_cog = self.cog.bot.get_cog('AntiNukeCog')
            if antinuke_cog:
                antinuke_cog.antinuke_enabled = True
                results['antinuke'] = True
            
            # Configure anti-raid
            antiraid_cog = self.cog.bot.get_cog('AntiRaidCog')
            if antiraid_cog:
                antiraid_cog.raid_protection_enabled = True
                results['antiraid'] = True
            
            # Set up quarantine role
            quarantine_cog = self.cog.bot.get_cog('QuarantineCog')
            if quarantine_cog:
                quarantine_role = await quarantine_cog.setup_quarantine_role(guild)
                results['quarantine'] = quarantine_role is not None
            
            # Create initial backup
            backup_cog = self.cog.bot.get_cog('BackupCog')
            if backup_cog:
                backup_data = await backup_cog.create_backup(guild)
                if backup_data:
                    self.cog.db.store_backup(backup_data)
                    results['backup'] = True
            
            # Final results
            success_count = sum(results.values())
            
            embed = discord.Embed(
                title="✅ Setup Complete!" if success_count > 3 else "⚠️ Setup Partially Complete",
                description=f"Configured {success_count}/5 security features",
                color=0x2ecc71 if success_count > 3 else 0xf39c12
            )
            
            status_emoji = lambda x: "✅" if x else "❌"
            
            embed.add_field(
                name="🛡️ Configured Features",
                value=f"{status_emoji(results['antinuke'])} Anti-Nuke Protection\n"
                      f"{status_emoji(results['antiraid'])} Anti-Raid Protection\n"
                      f"{status_emoji(results['quarantine'])} Quarantine System\n"
                      f"{status_emoji(results['backup'])} Initial Backup\n"
                      f"{status_emoji(results['verification'])} Verification System",
                inline=False
            )
            
            embed.add_field(
                name="📝 Next Steps",
                value="• Review `/antinuke status` for configuration\n"
                      "• Set up verification with `/verification`\n"
                      "• Configure automod with `/automod_status`\n"
                      "• Add trusted staff with `/immune add`",
                inline=False
            )
            
            await interaction.edit_original_response(embed=embed)
            
            # Log setup
            self.cog.db.log_action(
                "setup_wizard",
                interaction.user.id,
                None,
                f"Setup completed: {success_count}/5 features configured"
            )
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An error occurred during setup: {str(e)}",
                color=0xe74c3c
            )
            await interaction.edit_original_response(embed=embed)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Security setup has been cancelled. You can run `/setup` again anytime.",
            color=0x95a5a6
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))