import discord
from discord.ext import commands
from datetime import datetime
from utils.database import Database

class LoggingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Log when a member joins"""
        self.db.log_action("member_join", None, member.id, f"User joined the server")
        
        # Try to send to log channel
        await self.send_log(
            member.guild,
            "Member Joined",
            f"**{member}** joined the server",
            0x2ecc71,
            [
                ("Account Created", member.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), True),
                ("User ID", str(member.id), True)
            ]
        )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Log when a member leaves"""
        self.db.log_action("member_leave", None, member.id, f"User left the server")
        
        # Try to send to log channel
        await self.send_log(
            member.guild,
            "Member Left",
            f"**{member}** left the server",
            0xe74c3c,
            [
                ("Joined At", member.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if member.joined_at else "Unknown", True),
                ("User ID", str(member.id), True)
            ]
        )
    
    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """Log when a message is deleted"""
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return
        
        # Don't log empty messages or messages without content
        if not message.content and not message.attachments:
            return
        
        self.db.log_action("message_delete", None, message.author.id, f"Message deleted in #{message.channel.name}")
        
        # Prepare content preview
        content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
        if not content_preview and message.attachments:
            content_preview = f"[{len(message.attachments)} attachment(s)]"
        
        await self.send_log(
            message.guild,
            "Message Deleted",
            f"Message by **{message.author}** deleted in {message.channel.mention}",
            0xf39c12,
            [
                ("Content", content_preview or "No content", False),
                ("Author ID", str(message.author.id), True),
                ("Channel", message.channel.mention, True)
            ]
        )
    
    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """Log when a message is edited"""
        # Ignore bot messages, DMs, and if content is the same
        if before.author.bot or not before.guild or before.content == after.content:
            return
        
        # Ignore empty messages
        if not before.content and not after.content:
            return
        
        self.db.log_action("message_edit", None, before.author.id, f"Message edited in #{before.channel.name}")
        
        # Prepare content previews
        before_preview = before.content[:100] + "..." if len(before.content) > 100 else before.content
        after_preview = after.content[:100] + "..." if len(after.content) > 100 else after.content
        
        await self.send_log(
            before.guild,
            "Message Edited",
            f"Message by **{before.author}** edited in {before.channel.mention}",
            0x3498db,
            [
                ("Before", before_preview or "No content", False),
                ("After", after_preview or "No content", False),
                ("Author ID", str(before.author.id), True),
                ("Channel", before.channel.mention, True)
            ]
        )
    
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        """Log when a member is banned"""
        self.db.log_action("member_ban", None, user.id, f"User was banned")
        
        await self.send_log(
            guild,
            "Member Banned",
            f"**{user}** was banned from the server",
            0xe74c3c,
            [
                ("User ID", str(user.id), True)
            ]
        )
    
    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        """Log when a member is unbanned"""
        self.db.log_action("member_unban", None, user.id, f"User was unbanned")
        
        await self.send_log(
            guild,
            "Member Unbanned",
            f"**{user}** was unbanned from the server",
            0x2ecc71,
            [
                ("User ID", str(user.id), True)
            ]
        )
    
    async def send_log(self, guild, title, description, color, fields=None):
        """Send a log message to the log channel"""
        # Try to find a log channel
        log_channel = None
        for channel_name in ["mod-log", "modlog", "logs", "audit-log"]:
            log_channel = discord.utils.get(guild.channels, name=channel_name)
            if log_channel:
                break
        
        if not log_channel:
            return  # No log channel found
        
        try:
            embed = discord.Embed(
                title=f"📋 {title}",
                description=description,
                color=color,
                timestamp=datetime.utcnow()
            )
            
            if fields:
                for name, value, inline in fields:
                    embed.add_field(name=name, value=value, inline=inline)
            
            embed.set_footer(text="Security Bot Logging")
            
            await log_channel.send(embed=embed)
            
        except discord.Forbidden:
            pass  # Bot doesn't have permission to send messages
        except Exception as e:
            print(f"Error sending log message: {e}")
    
    @discord.app_commands.command(name="logs", description="View recent moderation logs")
    @discord.app_commands.describe(
        limit="Number of logs to show (max 10)",
        user="Filter logs for a specific user"
    )
    async def view_logs(self, interaction: discord.Interaction, limit: int = 5, user: discord.Member | None = None):
        """View recent moderation logs"""
        from utils.permissions import has_permission
        
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to view logs.", ephemeral=True)
            return
        
        if limit > 10:
            limit = 10
        elif limit < 1:
            limit = 1
        
        try:
            logs = self.db.get_recent_logs(limit, user.id if user else None)
            
            if not logs:
                embed = discord.Embed(
                    title="📋 No Logs Found",
                    description="No recent logs to display.",
                    color=0x95a5a6
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title="📋 Recent Moderation Logs",
                description=f"Showing last {len(logs)} log entries" + (f" for {user}" if user else ""),
                color=0x3498db
            )
            
            for log in logs:
                target_user = self.bot.get_user(log['target_id']) if log['target_id'] else None
                moderator = self.bot.get_user(log['moderator_id']) if log['moderator_id'] else None
                
                target_name = target_user.name if target_user else f"ID: {log['target_id']}" if log['target_id'] else "System"
                moderator_name = moderator.name if moderator else "System"
                
                embed.add_field(
                    name=f"{log['action'].replace('_', ' ').title()}",
                    value=f"**Target:** {target_name}\n"
                          f"**Moderator:** {moderator_name}\n"
                          f"**Reason:** {log['reason'][:50]}{'...' if len(log['reason']) > 50 else ''}\n"
                          f"**Time:** {log['timestamp'][:19]}",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(LoggingCog(bot))
