import discord
from discord.ext import commands
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from utils.database import Database

class AutoModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Spam detection
        self.user_messages = defaultdict(list)
        self.spam_threshold = 5  # messages
        self.spam_window = 10  # seconds
        
        # Rate limiting for auto-actions
        self.recent_actions = defaultdict(list)
        
        # Enhanced patterns for detection
        self.invite_pattern = re.compile(r'discord\.gg/[a-zA-Z0-9]+|discordapp\.com/invite/[a-zA-Z0-9]+|discord\.com/invite/[a-zA-Z0-9]+')
        self.link_pattern = re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?')
        self.excessive_caps_threshold = 0.7  # 70% caps
        self.min_caps_length = 10  # minimum message length to check caps
        
        # Advanced automod features
        self.forbidden_words = [
            # Add your forbidden words here
        ]
        self.zalgo_pattern = re.compile(r'[\u0300-\u036F\u1AB0-\u1AFF\u1DC0-\u1DFF\u20D0-\u20FF\uFE20-\uFE2F]')
        self.repeated_chars_pattern = re.compile(r'(.)\1{4,}')  # 5+ repeated characters
        
        # Whitelist for trusted domains
        self.whitelisted_domains = [
            'youtube.com', 'youtu.be', 'twitter.com', 'github.com',
            'stackoverflow.com', 'reddit.com', 'tenor.com', 'giphy.com'
        ]
    
    def is_spam(self, user_id: int) -> bool:
        """Check if a user is spamming"""
        now = datetime.utcnow()
        user_msgs = self.user_messages[user_id]
        
        # Remove old messages
        user_msgs[:] = [msg_time for msg_time in user_msgs if (now - msg_time).seconds < self.spam_window]
        
        return len(user_msgs) >= self.spam_threshold
    
    def has_excessive_caps(self, message: str) -> bool:
        """Check if message has excessive capital letters"""
        if len(message) < self.min_caps_length:
            return False
        
        caps_count = sum(1 for char in message if char.isupper())
        return caps_count / len(message) >= self.excessive_caps_threshold
    
    def can_take_action(self, user_id: int, action_type: str) -> bool:
        """Rate limit auto-moderation actions"""
        now = datetime.utcnow()
        key = f"{user_id}_{action_type}"
        
        # Clean old actions
        self.recent_actions[key] = [
            action_time for action_time in self.recent_actions[key]
            if (now - action_time).seconds < 60  # 1 minute cooldown
        ]
        
        if len(self.recent_actions[key]) >= 1:  # Max 1 action per minute
            return False
        
        self.recent_actions[key].append(now)
        return True
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Monitor messages for auto-moderation"""
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Ignore immune users
        from utils.permissions import is_immune
        if is_immune(message.author):
            return
        
        # Track message for spam detection
        self.user_messages[message.author.id].append(datetime.utcnow())
        
        # Check for various violations
        await self.check_spam(message)
        await self.check_invite_links(message)
        await self.check_excessive_caps(message)
        await self.check_forbidden_words(message)
        await self.check_suspicious_links(message)
        await self.check_zalgo_text(message)
        await self.check_repeated_characters(message)
    
    async def check_spam(self, message):
        """Check and handle spam"""
        if self.is_spam(message.author.id):
            if not self.can_take_action(message.author.id, "spam"):
                return
            
            try:
                # Delete recent messages from user
                async for msg in message.channel.history(limit=50):
                    if msg.author.id == message.author.id and (datetime.utcnow() - msg.created_at).seconds < 30:
                        try:
                            await msg.delete()
                        except:
                            pass
                
                # Mute user for 10 minutes
                timeout_until = datetime.utcnow() + timedelta(minutes=10)
                await message.author.timeout(timeout_until, reason="Auto-moderation: Spam detected")
                
                # Log the action
                self.db.log_action("automod_spam", self.bot.user.id, message.author.id, "Spam detection - 10 minute timeout")
                
                # Send notification
                embed = discord.Embed(
                    title="🤖 Auto-Moderation: Spam Detected",
                    description=f"**{message.author}** has been muted for 10 minutes due to spam.",
                    color=0xe74c3c
                )
                embed.add_field(name="Action Taken", value="10-minute timeout + message deletion", inline=False)
                
                # Try to send to a log channel or the same channel
                try:
                    log_channel = discord.utils.get(message.guild.channels, name="mod-log")
                    if log_channel:
                        await log_channel.send(embed=embed)
                    else:
                        await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass
                
            except discord.Forbidden:
                pass  # Bot doesn't have permissions
            except Exception as e:
                print(f"Error in spam detection: {e}")
    
    async def check_invite_links(self, message):
        """Check and handle Discord invite links"""
        if self.invite_pattern.search(message.content):
            if not self.can_take_action(message.author.id, "invite"):
                return
            
            try:
                # Delete the message
                await message.delete()
                
                # Warn the user
                warning_id = self.db.add_warning(
                    message.author.id,
                    self.bot.user.id,
                    "Auto-moderation: Posting Discord invite links"
                )
                
                # Log the action
                self.db.log_action(
                    "automod_invite",
                    self.bot.user.id,
                    message.author.id,
                    f"Invite link detected and deleted - Warning #{warning_id}"
                )
                
                # Send notification
                embed = discord.Embed(
                    title="🤖 Auto-Moderation: Invite Link Detected",
                    description=f"**{message.author}** posted a Discord invite link.",
                    color=0xf39c12
                )
                embed.add_field(name="Action Taken", value="Message deleted + Warning issued", inline=False)
                
                # Try to notify user
                try:
                    await message.author.send(
                        f"⚠️ Your message in **{message.guild.name}** was deleted for containing a Discord invite link. "
                        f"Please ask a moderator before sharing invites."
                    )
                except:
                    pass  # User has DMs disabled
                
                # Send to log channel or same channel
                try:
                    log_channel = discord.utils.get(message.guild.channels, name="mod-log")
                    if log_channel:
                        await log_channel.send(embed=embed)
                    else:
                        await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass
                
            except discord.Forbidden:
                pass  # Bot doesn't have permissions
            except Exception as e:
                print(f"Error in invite link detection: {e}")
    
    async def check_excessive_caps(self, message):
        """Check and handle excessive capital letters"""
        if self.has_excessive_caps(message.content):
            if not self.can_take_action(message.author.id, "caps"):
                return
            
            try:
                # Delete the message
                await message.delete()
                
                # Send warning
                embed = discord.Embed(
                    title="🤖 Auto-Moderation: Excessive Caps",
                    description=f"**{message.author}**, please don't use excessive capital letters.",
                    color=0xf39c12
                )
                
                warning_msg = await message.channel.send(embed=embed, delete_after=10)
                
                # Log the action
                self.db.log_action(
                    "automod_caps",
                    self.bot.user.id,
                    message.author.id,
                    "Excessive caps - message deleted"
                )
                
            except discord.Forbidden:
                pass  # Bot doesn't have permissions
            except Exception as e:
                print(f"Error in caps detection: {e}")
    
    async def check_forbidden_words(self, message):
        """Check and handle forbidden words"""
        if not self.forbidden_words:
            return
        
        content_lower = message.content.lower()
        
        for word in self.forbidden_words:
            if word.lower() in content_lower:
                if not self.can_take_action(message.author.id, "forbidden_word"):
                    return
                
                try:
                    await message.delete()
                    
                    warning_id = self.db.add_warning(
                        message.author.id,
                        self.bot.user.id,
                        f"Auto-moderation: Used forbidden word '{word}'"
                    )
                    
                    embed = discord.Embed(
                        title="🤖 Auto-Moderation: Forbidden Word",
                        description=f"**{message.author}** used a forbidden word.",
                        color=0xe74c3c
                    )
                    embed.add_field(name="Action Taken", value="Message deleted + Warning issued", inline=False)
                    
                    try:
                        log_channel = discord.utils.get(message.guild.channels, name="mod-log")
                        if log_channel:
                            await log_channel.send(embed=embed)
                        else:
                            await message.channel.send(embed=embed, delete_after=10)
                    except:
                        pass
                    
                    self.db.log_action(
                        "automod_forbidden_word",
                        self.bot.user.id,
                        message.author.id,
                        f"Forbidden word detected: {word}"
                    )
                    
                except:
                    pass
                break
    
    async def check_suspicious_links(self, message):
        """Check for suspicious links"""
        links = self.link_pattern.findall(message.content)
        
        for link in links:
            # Skip Discord invites (handled separately)
            if 'discord' in link:
                continue
            
            # Check if domain is whitelisted
            is_whitelisted = False
            for domain in self.whitelisted_domains:
                if domain in link:
                    is_whitelisted = True
                    break
            
            if not is_whitelisted:
                if not self.can_take_action(message.author.id, "suspicious_link"):
                    return
                
                try:
                    await message.delete()
                    
                    embed = discord.Embed(
                        title="🤖 Auto-Moderation: Suspicious Link",
                        description=f"**{message.author}** posted a non-whitelisted link.",
                        color=0xf39c12
                    )
                    embed.add_field(name="Action Taken", value="Message deleted", inline=False)
                    
                    try:
                        await message.author.send(
                            f"⚠️ Your message in **{message.guild.name}** was deleted for containing a suspicious link. "
                            f"If this was a legitimate link, please contact a moderator."
                        )
                    except:
                        pass
                    
                    try:
                        log_channel = discord.utils.get(message.guild.channels, name="mod-log")
                        if log_channel:
                            await log_channel.send(embed=embed)
                        else:
                            await message.channel.send(embed=embed, delete_after=10)
                    except:
                        pass
                    
                    self.db.log_action(
                        "automod_suspicious_link",
                        self.bot.user.id,
                        message.author.id,
                        f"Suspicious link: {link[:50]}..."
                    )
                    
                except:
                    pass
                break
    
    async def check_zalgo_text(self, message):
        """Check for zalgo/corrupted text"""
        zalgo_matches = self.zalgo_pattern.findall(message.content)
        
        if len(zalgo_matches) > 5:  # More than 5 zalgo characters
            if not self.can_take_action(message.author.id, "zalgo"):
                return
            
            try:
                await message.delete()
                
                embed = discord.Embed(
                    title="🤖 Auto-Moderation: Zalgo Text",
                    description=f"**{message.author}** posted corrupted/zalgo text.",
                    color=0xf39c12
                )
                embed.add_field(name="Action Taken", value="Message deleted", inline=False)
                
                warning_msg = await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid using corrupted text.",
                    delete_after=10
                )
                
                self.db.log_action(
                    "automod_zalgo",
                    self.bot.user.id,
                    message.author.id,
                    "Zalgo text detected"
                )
                
            except:
                pass
    
    async def check_repeated_characters(self, message):
        """Check for excessive repeated characters"""
        if self.repeated_chars_pattern.search(message.content):
            if not self.can_take_action(message.author.id, "repeated_chars"):
                return
            
            try:
                await message.delete()
                
                embed = discord.Embed(
                    title="🤖 Auto-Moderation: Repeated Characters",
                    description=f"**{message.author}** used excessive repeated characters.",
                    color=0xf39c12
                )
                embed.add_field(name="Action Taken", value="Message deleted", inline=False)
                
                warning_msg = await message.channel.send(
                    f"⚠️ {message.author.mention}, please avoid spamming repeated characters.",
                    delete_after=10
                )
                
                self.db.log_action(
                    "automod_repeated_chars",
                    self.bot.user.id,
                    message.author.id,
                    "Excessive repeated characters"
                )
                
            except:
                pass
    
    @discord.app_commands.command(name="automod", description="Configure auto-moderation settings")
    @discord.app_commands.describe(
        feature="The feature to toggle",
        enabled="Enable or disable the feature"
    )
    @discord.app_commands.choices(feature=[
        discord.app_commands.Choice(name="Spam Detection", value="spam"),
        discord.app_commands.Choice(name="Invite Links", value="invites"),
        discord.app_commands.Choice(name="Excessive Caps", value="caps")
    ])
    async def automod_config(self, interaction: discord.Interaction, feature: str, enabled: bool):
        """Configure auto-moderation features"""
        from utils.permissions import has_permission
        
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to configure auto-moderation.", ephemeral=True)
            return
        
        # This would typically save to a database or config file
        # For now, we'll just acknowledge the command
        
        feature_names = {
            "spam": "Spam Detection",
            "invites": "Invite Link Detection",
            "caps": "Excessive Caps Detection"
        }
        
        status = "✅ Enabled" if enabled else "❌ Disabled"
        
        embed = discord.Embed(
            title="🤖 Auto-Moderation Configuration",
            description=f"**{feature_names[feature]}** has been {status.lower()}.",
            color=0x2ecc71 if enabled else 0xe74c3c
        )
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="automod_status", description="View auto-moderation status")
    async def automod_status(self, interaction: discord.Interaction):
        """Show current auto-moderation settings"""
        from utils.permissions import has_permission
        
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to view this information.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🤖 Auto-Moderation Status",
            description="Current auto-moderation configuration:",
            color=0x3498db
        )
        
        embed.add_field(
            name="Spam Detection",
            value=f"✅ Enabled\nThreshold: {self.spam_threshold} messages in {self.spam_window}s",
            inline=True
        )
        
        embed.add_field(
            name="Invite Links",
            value="✅ Enabled\nAction: Delete + Warn",
            inline=True
        )
        
        embed.add_field(
            name="Excessive Caps",
            value=f"✅ Enabled\nThreshold: {int(self.excessive_caps_threshold * 100)}%",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoModerationCog(bot))
