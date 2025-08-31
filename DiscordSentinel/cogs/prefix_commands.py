import discord
from discord.ext import commands
from datetime import datetime, timedelta
from utils.database import Database
from utils.permissions import has_permission, is_immune

class PrefixCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @commands.command(name="ban")
    async def ban_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Ban a user from the server"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to ban users.")
            return
        
        if is_immune(member):
            await ctx.send("❌ Cannot ban this user (immune role).")
            return
        
        try:
            await member.ban(reason=f"Banned by {ctx.author} | {reason}")
            
            embed = discord.Embed(
                title="🔨 User Banned",
                description=f"**{member}** has been banned from the server.",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
            # Log the action
            self.db.log_action("ban", ctx.author.id, member.id, reason)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="kick")
    async def kick_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Kick a user from the server"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to kick users.")
            return
        
        if is_immune(member):
            await ctx.send("❌ Cannot kick this user (immune role).")
            return
        
        try:
            await member.kick(reason=f"Kicked by {ctx.author} | {reason}")
            
            embed = discord.Embed(
                title="👢 User Kicked",
                description=f"**{member}** has been kicked from the server.",
                color=0xf39c12
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
            # Log the action
            self.db.log_action("kick", ctx.author.id, member.id, reason)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to kick this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="warn")
    async def warn_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Issue a warning to a user"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to warn users.")
            return
        
        if is_immune(member):
            await ctx.send("❌ Cannot warn this user (immune role).")
            return
        
        # Add warning to database
        warning_id = self.db.add_warning(member.id, ctx.author.id, reason)
        
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"**{member}** has been warned.",
            color=0xf39c12
        )
        embed.add_field(name="Warning ID", value=f"#{warning_id}", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        # Get total warnings
        total_warnings = self.db.get_warning_count(member.id)
        embed.add_field(name="Total Warnings", value=total_warnings, inline=True)
        
        await ctx.send(embed=embed)
        
        # Try to DM the user
        try:
            dm_embed = discord.Embed(
                title="⚠️ You received a warning",
                description=f"You were warned in **{ctx.guild.name}**",
                color=0xf39c12
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.add_field(name="Warning ID", value=f"#{warning_id}", inline=True)
            dm_embed.add_field(name="Total Warnings", value=total_warnings, inline=True)
            
            await member.send(embed=dm_embed)
        except:
            pass  # User has DMs disabled
    
    @commands.command(name="warnings")
    async def warnings_command(self, ctx, member: discord.Member = None):
        """View warnings for a user"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to view warnings.")
            return
        
        target = member or ctx.author
        warnings = self.db.get_warnings(target.id)
        
        if not warnings:
            embed = discord.Embed(
                title="⚠️ No Warnings",
                description=f"**{target}** has no warnings.",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title=f"⚠️ Warnings for {target}",
            description=f"**{len(warnings)}** warning(s) found",
            color=0xf39c12
        )
        
        for warning in warnings[-5:]:  # Show last 5 warnings
            moderator = self.bot.get_user(warning['moderator_id'])
            moderator_name = moderator.name if moderator else "Unknown"
            
            embed.add_field(
                name=f"Warning #{warning['id']}",
                value=f"**Reason:** {warning['reason']}\n"
                      f"**Moderator:** {moderator_name}\n"
                      f"**Date:** {warning['timestamp'][:10]}",
                inline=False
            )
        
        if len(warnings) > 5:
            embed.set_footer(text=f"Showing 5 of {len(warnings)} warnings")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="mute")
    async def mute_command(self, ctx, member: discord.Member, duration: str = "1h", *, reason="No reason provided"):
        """Timeout a user"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to mute users.")
            return
        
        if is_immune(member):
            await ctx.send("❌ Cannot mute this user (immune role).")
            return
        
        # Parse duration
        try:
            if duration.endswith('m'):
                minutes = int(duration[:-1])
                timeout_duration = discord.utils.utcnow() + timedelta(minutes=minutes)
            elif duration.endswith('h'):
                hours = int(duration[:-1])
                timeout_duration = discord.utils.utcnow() + timedelta(hours=hours)
            elif duration.endswith('d'):
                days = int(duration[:-1])
                timeout_duration = discord.utils.utcnow() + timedelta(days=days)
            else:
                minutes = int(duration)
                timeout_duration = discord.utils.utcnow() + timedelta(minutes=minutes)
        except ValueError:
            await ctx.send("❌ Invalid duration format. Use: 30m, 2h, 1d, or just numbers for minutes.")
            return
        
        try:
            await member.edit(timed_out_until=timeout_duration, reason=f"Muted by {ctx.author} | {reason}")
            
            embed = discord.Embed(
                title="🔇 User Muted",
                description=f"**{member}** has been muted.",
                color=0xf39c12
            )
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
            # Log the action
            self.db.log_action("mute", ctx.author.id, member.id, f"{reason} | Duration: {duration}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to mute this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="unmute")
    async def unmute_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Remove timeout from a user"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to unmute users.")
            return
        
        try:
            await member.edit(timed_out_until=None, reason=f"Unmuted by {ctx.author} | {reason}")
            
            embed = discord.Embed(
                title="🔊 User Unmuted",
                description=f"**{member}** has been unmuted.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
            # Log the action
            self.db.log_action("unmute", ctx.author.id, member.id, reason)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to unmute this user.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="purge", aliases=["clear"])
    async def purge_command(self, ctx, amount: int = 10, member: discord.Member = None):
        """Delete messages from the channel"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to purge messages.")
            return
        
        if amount > 100:
            await ctx.send("❌ Cannot purge more than 100 messages at once.")
            return
        
        def check(message):
            if member:
                return message.author == member
            return True
        
        try:
            deleted = await ctx.channel.purge(limit=amount + 1, check=check)  # +1 for the command message
            
            embed = discord.Embed(
                title="🧹 Messages Purged",
                description=f"Deleted **{len(deleted) - 1}** messages",
                color=0x3498db
            )
            
            if member:
                embed.add_field(name="Target User", value=member.mention, inline=True)
            
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            # Send confirmation and delete after 5 seconds
            confirmation = await ctx.send(embed=embed, delete_after=5)
            
            # Log the action
            target_info = f" from {member}" if member else ""
            self.db.log_action("purge", ctx.author.id, member.id if member else None, 
                             f"Purged {len(deleted) - 1} messages{target_info}")
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="lockdown")
    async def lockdown_command(self, ctx, *, reason="Emergency lockdown"):
        """Lock down the entire server"""
        if not has_permission(ctx.author, 'admin'):
            await ctx.send("❌ You need admin permissions to lockdown the server.")
            return
        
        try:
            locked_channels = 0
            
            for channel in ctx.guild.text_channels:
                try:
                    overwrite = discord.PermissionOverwrite()
                    overwrite.send_messages = False
                    overwrite.add_reactions = False
                    
                    await channel.set_permissions(
                        ctx.guild.default_role,
                        overwrite=overwrite,
                        reason=f"Server lockdown by {ctx.author} | {reason}"
                    )
                    locked_channels += 1
                except:
                    continue
            
            embed = discord.Embed(
                title="🔒 Server Lockdown Activated",
                description=f"Server has been locked down by {ctx.author.mention}",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Channels Locked", value=locked_channels, inline=True)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
            # Log the action
            self.db.log_action("lockdown", ctx.author.id, None, f"Server lockdown | {reason}")
            
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="help")
    async def help_command(self, ctx, command_name: str = None):
        """Show help for commands"""
        if command_name:
            # Show help for specific command
            command = self.bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"📖 Help: !{command.name}",
                    description=command.help or "No description available",
                    color=0x3498db
                )
                
                if command.aliases:
                    embed.add_field(name="Aliases", value=", ".join([f"!{alias}" for alias in command.aliases]), inline=False)
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Command `{command_name}` not found.")
            return
        
        # Show general help
        embed = discord.Embed(
            title="🛡️ AegisGuard Prefix Commands",
            description="Available prefix commands (use `!` prefix):",
            color=0x3498db
        )
        
        embed.add_field(
            name="**🔨 Moderation**",
            value="`!ban` `!kick` `!warn` `!warnings`\n"
                  "`!mute` `!unmute` `!purge`\n"
                  "`!quarantine` `!unquarantine`\n"
                  "`!massban`",
            inline=True
        )
        
        embed.add_field(
            name="**🛡️ Security**",
            value="`!lockdown` `!lock` `!unlock`\n"
                  "`!antiraid` `!antinuke`\n"
                  "`!backup create` `!backup list`",
            inline=True
        )
        
        embed.add_field(
            name="**📊 Utility**",
            value="`!info` `!about` `!ping`\n"
                  "`!slowmode` `!help`\n"
                  "`!help <command>` - Command help",
            inline=True
        )
        
        embed.add_field(
            name="**💡 All Features Available**",
            value="✅ Complete feature parity with slash commands\n"
                  "Use `!` for quick commands or `/` for advanced features",
            inline=False
        )
        
        embed.set_footer(text="AegisGuard | Prefix Commands")
        await ctx.send(embed=embed)
    
    @commands.command(name="quarantine")
    async def quarantine_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Quarantine a user (AegisGuard's signature isolation)"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to quarantine users.")
            return
        
        if is_immune(member):
            await ctx.send("❌ Cannot quarantine this user (immune role).")
            return
        
        # Get quarantine cog
        quarantine_cog = self.bot.get_cog('QuarantineCog')
        if not quarantine_cog:
            await ctx.send("❌ Quarantine system not available.")
            return
        
        success = await quarantine_cog.quarantine_user(member, ctx.author, reason)
        
        if success:
            embed = discord.Embed(
                title="🔒 User Quarantined",
                description=f"**{member}** has been isolated in quarantine.",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            embed.add_field(
                name="⚠️ Quarantine Effects",
                value="• User cannot see any channels\n"
                      "• User cannot send messages\n"
                      "• User cannot join voice channels\n"
                      "• All original roles removed",
                inline=False
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to quarantine user. Check bot permissions.")
    
    @commands.command(name="unquarantine")
    async def unquarantine_command(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Remove a user from quarantine"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You don't have permission to unquarantine users.")
            return
        
        # Get quarantine cog
        quarantine_cog = self.bot.get_cog('QuarantineCog')
        if not quarantine_cog:
            await ctx.send("❌ Quarantine system not available.")
            return
        
        success = await quarantine_cog.unquarantine_user(member, ctx.author, reason)
        
        if success:
            embed = discord.Embed(
                title="🔓 User Unquarantined",
                description=f"**{member}** has been released from quarantine.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to unquarantine user.")
    
    @commands.command(name="antiraid")
    async def antiraid_command(self, ctx, action: str = "status"):
        """Configure anti-raid protection"""
        if not has_permission(ctx.author, 'admin') and action != "status":
            await ctx.send("❌ You need admin permissions to configure anti-raid.")
            return
        
        antiraid_cog = self.bot.get_cog('AntiRaidCog')
        if not antiraid_cog:
            await ctx.send("❌ Anti-raid system not available.")
            return
        
        if action.lower() == "on":
            antiraid_cog.raid_protection_enabled = True
            await ctx.send("✅ Anti-raid protection **enabled**.")
        elif action.lower() == "off":
            antiraid_cog.raid_protection_enabled = False
            await ctx.send("❌ Anti-raid protection **disabled**.")
        else:
            # Show status
            status = "🟢 Enabled" if antiraid_cog.raid_protection_enabled else "🔴 Disabled"
            embed = discord.Embed(
                title="🚨 Anti-Raid Status",
                description=f"Protection: {status}",
                color=0x2ecc71 if antiraid_cog.raid_protection_enabled else 0xe74c3c
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="antinuke")
    async def antinuke_command(self, ctx, action: str = "status"):
        """Configure anti-nuke protection"""
        if not has_permission(ctx.author, 'admin') and action != "status":
            await ctx.send("❌ You need admin permissions to configure anti-nuke.")
            return
        
        antinuke_cog = self.bot.get_cog('AntiNukeCog')
        if not antinuke_cog:
            await ctx.send("❌ Anti-nuke system not available.")
            return
        
        if action.lower() == "on":
            antinuke_cog.antinuke_enabled = True
            await ctx.send("✅ Anti-nuke protection **enabled**.")
        elif action.lower() == "off":
            antinuke_cog.antinuke_enabled = False
            await ctx.send("❌ Anti-nuke protection **disabled**.")
        else:
            # Show status
            status = "🟢 Active" if antinuke_cog.antinuke_enabled else "🔴 Disabled"
            panic_status = "🚨 ACTIVE" if antinuke_cog.panic_mode else "✅ Normal"
            
            embed = discord.Embed(
                title="🛡️ Anti-Nuke Status",
                color=0x3498db
            )
            embed.add_field(name="Protection Status", value=status, inline=True)
            embed.add_field(name="Panic Mode", value=panic_status, inline=True)
            
            await ctx.send(embed=embed)
    
    @commands.command(name="backup")
    async def backup_command(self, ctx, action: str = "create"):
        """Create or manage server backups"""
        if not has_permission(ctx.author, 'admin'):
            await ctx.send("❌ You need admin permissions to manage backups.")
            return
        
        backup_cog = self.bot.get_cog('BackupCog')
        if not backup_cog:
            await ctx.send("❌ Backup system not available.")
            return
        
        if action.lower() == "create":
            embed = discord.Embed(
                title="💾 Creating Backup",
                description="Creating comprehensive server backup...",
                color=0xf39c12
            )
            
            status_msg = await ctx.send(embed=embed)
            
            backup_data = await backup_cog.create_backup(ctx.guild)
            
            if backup_data:
                backup_id = self.db.store_backup(backup_data)
                
                embed = discord.Embed(
                    title="✅ Backup Created",
                    description=f"Server backup created successfully!",
                    color=0x2ecc71
                )
                
                embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
                embed.add_field(name="Channels", value=len(backup_data["channels"]), inline=True)
                embed.add_field(name="Roles", value=len(backup_data["roles"]), inline=True)
                
                await status_msg.edit(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Backup Failed",
                    description="Failed to create server backup.",
                    color=0xe74c3c
                )
                await status_msg.edit(embed=embed)
        
        elif action.lower() == "list":
            backups = self.db.get_backups(ctx.guild.id)
            
            if not backups:
                await ctx.send("💾 No backups found for this server.")
                return
            
            embed = discord.Embed(
                title="💾 Server Backups",
                description=f"Found {len(backups)} backup(s)",
                color=0x3498db
            )
            
            for backup in backups[:5]:
                timestamp = backup["timestamp"][:19]
                embed.add_field(
                    name=f"📁 {backup['id']}",
                    value=f"**Date:** {timestamp}\n"
                          f"**Items:** {len(backup['channels'])} channels, {len(backup['roles'])} roles",
                    inline=True
                )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Invalid action. Use: `!backup create` or `!backup list`")
    
    @commands.command(name="info")
    async def info_command(self, ctx, *, target: str = None):
        """Get detailed information about users, roles, or server"""
        info_cog = self.bot.get_cog('InfoCog')
        if not info_cog:
            await ctx.send("❌ Info system not available.")
            return
        
        if not target:
            # Default to user who ran command
            await info_cog.show_user_info(ctx, ctx.author)
            return
        
        # Check if target is "server"
        if target.lower() == "server":
            await info_cog.show_server_info(ctx)
            return
        
        # Try to find user or role
        # Try user mention or ID
        try:
            if target.startswith("<@") and target.endswith(">"):
                user_id = int(target[2:-1].replace("!", ""))
            else:
                user_id = int(target)
            
            user = ctx.guild.get_member(user_id)
            if user:
                await info_cog.show_user_info(ctx, user)
                return
        except ValueError:
            pass
        
        # Try username
        user = discord.utils.get(ctx.guild.members, name=target)
        if user:
            await info_cog.show_user_info(ctx, user)
            return
        
        # Try role
        try:
            if target.startswith("<@&") and target.endswith(">"):
                role_id = int(target[3:-1])
                role = ctx.guild.get_role(role_id)
            else:
                role = discord.utils.get(ctx.guild.roles, name=target)
            
            if role:
                await info_cog.show_role_info(ctx, role)
                return
        except ValueError:
            pass
        
        await ctx.send("❌ User, role, or 'server' not found.")
    
    @commands.command(name="slowmode")
    async def slowmode_command(self, ctx, seconds: int = 0, duration: int = 0):
        """Set channel slowmode with optional duration"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You need moderator permissions to manage slowmode.")
            return
        
        if seconds < 0 or seconds > 21600:
            await ctx.send("❌ Slowmode must be between 0 and 21600 seconds (6 hours).")
            return
        
        try:
            await ctx.channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode set by {ctx.author}"
            )
            
            if seconds == 0:
                embed = discord.Embed(
                    title="🐌 Slowmode Disabled",
                    description=f"Slowmode has been disabled in {ctx.channel.mention}",
                    color=0x2ecc71
                )
            else:
                embed = discord.Embed(
                    title="🐌 Slowmode Enabled",
                    description=f"Slowmode set to **{seconds} seconds** in {ctx.channel.mention}",
                    color=0x3498db
                )
                
                if duration > 0:
                    embed.add_field(
                        name="⏰ Duration",
                        value=f"Will be disabled in {duration} minutes",
                        inline=False
                    )
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="lock")
    async def lock_command(self, ctx, *, reason="No reason provided"):
        """Lock a channel to prevent messages"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You need moderator permissions to lock channels.")
            return
        
        try:
            overwrite = discord.PermissionOverwrite()
            overwrite.send_messages = False
            overwrite.add_reactions = False
            
            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=f"Channel locked by {ctx.author} | {reason}"
            )
            
            embed = discord.Embed(
                title="🔒 Channel Locked",
                description=f"{ctx.channel.mention} has been locked.",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="unlock")
    async def unlock_command(self, ctx, *, reason="No reason provided"):
        """Unlock a channel to allow messages"""
        if not has_permission(ctx.author, 'moderator'):
            await ctx.send("❌ You need moderator permissions to unlock channels.")
            return
        
        try:
            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=None,
                reason=f"Channel unlocked by {ctx.author} | {reason}"
            )
            
            embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description=f"{ctx.channel.mention} has been unlocked.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
            
            await ctx.send(embed=embed)
            
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to manage this channel.")
        except Exception as e:
            await ctx.send(f"❌ An error occurred: {str(e)}")
    
    @commands.command(name="massban")
    async def massban_command(self, ctx, *user_ids):
        """Mass ban users by ID"""
        if not has_permission(ctx.author, 'admin'):
            await ctx.send("❌ You need admin permissions to mass ban.")
            return
        
        if len(user_ids) > 50:
            await ctx.send("❌ Cannot ban more than 50 users at once.")
            return
        
        if not user_ids:
            await ctx.send("❌ Please provide user IDs to ban. Usage: `!massban 123456789 987654321`")
            return
        
        banned_count = 0
        failed_count = 0
        
        embed = discord.Embed(
            title="🔨 Mass Ban in Progress",
            description=f"Processing {len(user_ids)} user(s)...",
            color=0xf39c12
        )
        
        status_msg = await ctx.send(embed=embed)
        
        for user_id in user_ids:
            try:
                user_id = int(user_id)
                await ctx.guild.ban(discord.Object(id=user_id), reason=f"Mass ban by {ctx.author}")
                banned_count += 1
            except:
                failed_count += 1
        
        embed = discord.Embed(
            title="🔨 Mass Ban Complete",
            color=0x2ecc71 if failed_count == 0 else 0xf39c12
        )
        
        embed.add_field(name="✅ Successfully Banned", value=banned_count, inline=True)
        embed.add_field(name="❌ Failed", value=failed_count, inline=True)
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        
        await status_msg.edit(embed=embed)
    
    @commands.command(name="ping")
    async def ping_command(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=0x2ecc71 if latency < 100 else 0xf39c12 if latency < 200 else 0xe74c3c
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="about")
    async def about_command(self, ctx):
        """Show detailed information about the bot and owner"""
        owner = self.bot.get_user(self.bot.owner_id) if hasattr(self.bot, 'owner_id') else None
        if not owner:
            app_info = await self.bot.application_info()
            owner = app_info.owner
        
        embed = discord.Embed(
            title="🛡️ AegisGuard - Discord Security Bot",
            description="A comprehensive Discord moderation and security bot designed to keep your server safe.",
            color=0x3498db
        )
        
        # Bot information
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"**Servers:** {len(self.bot.guilds)}\n"
                  f"**Uptime:** {str(datetime.utcnow() - self.bot.start_time).split('.')[0]}\n"
                  f"**Latency:** {round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        # Features
        embed.add_field(
            name="🔧 Features",
            value="• Advanced Anti-Raid Protection\n"
                  "• Quarantine & Anti-Nuke Systems\n"
                  "• Mass Moderation Tools\n"
                  "• Auto-Moderation & Verification\n"
                  "• Backup & Restore Capabilities",
            inline=True
        )
        
        # Owner information
        embed.add_field(
            name="👤 Bot Owner",
            value=f"**Name:** {owner.name if owner else 'Unknown'}\n"
                  f"**ID:** {owner.id if owner else 'Unknown'}\n"
                  f"**Created:** {owner.created_at.strftime('%Y-%m-%d') if owner else 'Unknown'}",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)
        embed.set_footer(
            text=f"AegisGuard • Keeping your server secure",
            icon_url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="setup")
    async def setup_command(self, ctx):
        """Quick setup wizard for server security"""
        if not has_permission(ctx.author, 'admin'):
            await ctx.send("❌ You need admin permissions to run setup.")
            return
        
        # Initial setup embed
        embed = discord.Embed(
            title="🛠️ Server Security Setup",
            description="Starting security setup wizard...",
            color=0x3498db
        )
        
        status_msg = await ctx.send(embed=embed)
        
        # Configure features
        results = {
            'antinuke': False,
            'antiraid': False,
            'quarantine': False,
            'backup': False,
            'logs_channel': False
        }
        
        try:
            # Update status
            embed.description = "🔄 Configuring anti-nuke protection..."
            await status_msg.edit(embed=embed)
            
            # Configure anti-nuke
            antinuke_cog = self.bot.get_cog('AntiNukeCog')
            if antinuke_cog:
                antinuke_cog.antinuke_enabled = True
                results['antinuke'] = True
            
            # Update status
            embed.description = "🔄 Configuring anti-raid protection..."
            await status_msg.edit(embed=embed)
            
            # Configure anti-raid
            antiraid_cog = self.bot.get_cog('AntiRaidCog')
            if antiraid_cog:
                antiraid_cog.raid_protection_enabled = True
                results['antiraid'] = True
            
            # Update status
            embed.description = "🔄 Setting up quarantine system..."
            await status_msg.edit(embed=embed)
            
            # Set up quarantine role
            quarantine_cog = self.bot.get_cog('QuarantineCog')
            if quarantine_cog:
                quarantine_role = await quarantine_cog.setup_quarantine_role(ctx.guild)
                results['quarantine'] = quarantine_role is not None
            
            # Update status
            embed.description = "🔄 Setting up logs channel..."
            await status_msg.edit(embed=embed)
            
            # Create or find logs channel
            logs_channel = discord.utils.get(ctx.guild.text_channels, name="aegis-logs")
            if not logs_channel:
                try:
                    # Create the logs channel
                    overwrites = {
                        ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                    }
                    
                    # Add permission for moderator roles
                    for role in ctx.guild.roles:
                        if role.name.lower() in ['moderator', 'admin', 'staff', 'mod']:
                            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=False)
                    
                    logs_channel = await ctx.guild.create_text_channel(
                        'aegis-logs',
                        topic='🛡️ AegisGuard Security Logs - All moderation actions are logged here',
                        overwrites=overwrites,
                        reason='AegisGuard setup - Security logs channel'
                    )
                    
                    # Send welcome message to logs channel
                    embed_welcome = discord.Embed(
                        title="🛡️ AegisGuard Logs Channel",
                        description="This channel will track all security and moderation actions.",
                        color=0x3498db
                    )
                    embed_welcome.add_field(
                        name="📝 What gets logged:",
                        value="• Bans, kicks, and warnings\n"
                              "• Quarantine actions\n"
                              "• Anti-raid/anti-nuke alerts\n"
                              "• Channel locks and unlocks\n"
                              "• Mass moderation actions",
                        inline=False
                    )
                    await logs_channel.send(embed=embed_welcome)
                    
                    results['logs_channel'] = True
                except Exception as e:
                    print(f"Failed to create logs channel: {e}")
            else:
                results['logs_channel'] = True
            
            # Update status
            embed.description = "🔄 Creating server backup..."
            await status_msg.edit(embed=embed)
            
            # Create initial backup
            backup_cog = self.bot.get_cog('BackupCog')
            if backup_cog:
                backup_data = await backup_cog.create_backup(ctx.guild)
                if backup_data:
                    self.db.store_backup(backup_data)
                    results['backup'] = True
            
            # Final results
            success_count = sum(results.values())
            
            embed = discord.Embed(
                title="✅ Setup Complete!" if success_count > 3 else "⚠️ Setup Partially Complete",
                description=f"Configured {success_count}/5 security features",
                color=0x2ecc71 if success_count > 3 else 0xf39c12
            )
            
            status_text = []
            status_text.append(f"{'✅' if results['antinuke'] else '❌'} Anti-nuke protection")
            status_text.append(f"{'✅' if results['antiraid'] else '❌'} Anti-raid protection")
            status_text.append(f"{'✅' if results['quarantine'] else '❌'} Quarantine system")
            status_text.append(f"{'✅' if results['logs_channel'] else '❌'} Logs channel (#aegis-logs)")
            status_text.append(f"{'✅' if results['backup'] else '❌'} Server backup")
            
            embed.add_field(
                name="🛡️ Security Features",
                value="\n".join(status_text),
                inline=False
            )
            
            embed.add_field(
                name="🎯 Next Steps",
                value="• Use `!help` to see all available commands\n"
                      "• Configure auto-moderation with `/automod`\n"
                      "• Set up verification with `/verification`\n"
                      "• Test quarantine with `!quarantine @user`\n"
                      f"• Check security logs in {logs_channel.mention if logs_channel else '#aegis-logs'}",
                inline=False
            )
            
            await status_msg.edit(embed=embed)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Setup Failed",
                description=f"An error occurred during setup: {str(e)}",
                color=0xe74c3c
            )
            await status_msg.edit(embed=embed)
    
    @commands.command(name="invite")
    async def invite_command(self, ctx):
        """Get the bot invite link"""
        # Create bot invite URL with necessary permissions
        permissions = discord.Permissions(
            administrator=True,  # Full admin permissions for security bot
            manage_guild=True,
            manage_roles=True,
            manage_channels=True,
            kick_members=True,
            ban_members=True,
            manage_messages=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            moderate_members=True  # For timeout functionality
        )
        
        invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=permissions)
        
        embed = discord.Embed(
            title="🤖 Invite AegisGuard to Your Server",
            description="Click the link below to add AegisGuard to your Discord server!",
            color=0x3498db
        )
        
        embed.add_field(
            name="📋 Required Permissions",
            value="• Administrator (recommended)\n"
                  "• Manage Server & Roles\n"
                  "• Kick/Ban Members\n"
                  "• Manage Messages & Channels\n"
                  "• Moderate Members (timeouts)",
            inline=True
        )
        
        embed.add_field(
            name="🛡️ Security Features",
            value="• Advanced Anti-Raid Protection\n"
                  "• Quarantine & Anti-Nuke Systems\n"
                  "• Mass Moderation Tools\n"
                  "• Auto-Moderation & Verification\n"
                  "• Backup & Restore Capabilities",
            inline=True
        )
        
        embed.add_field(
            name="🚀 Quick Setup",
            value=f"After adding the bot, run `!setup` to automatically configure all security features in seconds!",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Invite Link",
            value=f"[**Click here to invite AegisGuard**]({invite_url})",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user and self.bot.user.avatar else None)
        embed.set_footer(text="AegisGuard | Enterprise Discord Security")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PrefixCommandsCog(bot))