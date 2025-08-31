import discord
from discord.ext import commands
import asyncio
import json
import os
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SecurityBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.start_time = datetime.utcnow()
        
    async def setup_hook(self):
        """Load all cogs when the bot starts"""
        try:
            await self.load_extension('cogs.moderation')
            await self.load_extension('cogs.automod')
            await self.load_extension('cogs.logging')
            await self.load_extension('cogs.antiraid')
            await self.load_extension('cogs.massmod')
            await self.load_extension('cogs.verification')
            await self.load_extension('cogs.quarantine')
            await self.load_extension('cogs.antinuke')
            await self.load_extension('cogs.backup')
            await self.load_extension('cogs.info')
            await self.load_extension('cogs.utility')
            await self.load_extension('cogs.prefix_commands')
            logger.info("All cogs loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cogs: {e}")
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready"""
        logger.info(f'{self.user} has logged in successfully!')
        logger.info(f'Bot ID: {self.user.id if self.user else "Unknown"}')
        logger.info(f'Connected to {len(self.guilds)} guilds')
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for security threats | !help"
            )
        )
    
    async def on_guild_join(self, guild):
        """Called when the bot joins a new guild"""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Send welcome message to the server channel
        welcome_channel = None
        
        # Try system channel first
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            welcome_channel = guild.system_channel
        else:
            # Find a suitable channel to send welcome message
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    if any(name in channel.name.lower() for name in ['general', 'welcome', 'main', 'chat']):
                        welcome_channel = channel
                        break
            
            # If no suitable named channel, use first available
            if not welcome_channel:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        welcome_channel = channel
                        break
        
        # Send welcome message to channel
        if welcome_channel:
            try:
                channel_embed = discord.Embed(
                    title="🛡️ AegisGuard Security Bot Added!",
                    description="Advanced Discord security protection is now active on this server.",
                    color=0x2ecc71
                )
                
                channel_embed.add_field(
                    name="🚀 Quick Setup",
                    value="Server admins: Run `!setup` to configure all security features automatically!",
                    inline=False
                )
                
                channel_embed.add_field(
                    name="📚 Commands",
                    value="`!help` - Show all prefix commands\n"
                          "`/help` - Show all slash commands\n"
                          "`!invite` - Get bot invite link",
                    inline=False
                )
                
                channel_embed.set_footer(text="AegisGuard | Keeping your server secure")
                
                await welcome_channel.send(embed=channel_embed)
                logger.info(f'Sent welcome message to #{welcome_channel.name} in {guild.name}')
            except Exception as e:
                logger.error(f'Failed to send welcome message to channel: {e}')
        
        # Send DM to server owner
        if guild.owner:
            try:
                owner_embed = discord.Embed(
                    title="🛡️ AegisGuard Added to Your Server",
                    description=f"Thank you for adding **AegisGuard** to **{guild.name}**!",
                    color=0x3498db
                )
                
                owner_embed.add_field(
                    name="⚡ Immediate Next Steps",
                    value="1. Run `!setup` in your server for automatic configuration\n"
                          "2. Review the created `#aegis-logs` channel\n"
                          "3. Test the quarantine system with `!quarantine @user`\n"
                          "4. Configure auto-moderation with `/automod`",
                    inline=False
                )
                
                owner_embed.add_field(
                    name="🔧 Advanced Features",
                    value="• **Anti-raid protection** - Automatic raid detection\n"
                          "• **Anti-nuke system** - Prevents server destruction\n"
                          "• **Quarantine isolation** - Advanced user containment\n"
                          "• **Mass moderation** - Bulk user management\n"
                          "• **Server backups** - Full restore capabilities",
                    inline=False
                )
                
                owner_embed.set_footer(text="AegisGuard | Enterprise Discord Security")
                
                await guild.owner.send(embed=owner_embed)
                logger.info(f'Sent welcome DM to server owner: {guild.owner}')
            except Exception as e:
                logger.error(f'Failed to send DM to server owner: {e}')
        
        # Send welcome DMs to members (limited to prevent spam)
        welcome_embed = discord.Embed(
            title="🛡️ AegisGuard Has Joined Your Server!",
            description=f"Hello! I'm **AegisGuard**, an advanced Discord security bot that just joined **{guild.name}**.",
            color=0x3498db
        )
        
        welcome_embed.add_field(
            name="🚀 What I Do",
            value="• **Anti-Raid & Anti-Nuke Protection**\n"
                  "• **Quarantine System** for isolating troublemakers\n"
                  "• **Mass Moderation Tools** for efficient management\n"
                  "• **Auto-Moderation** with smart spam detection\n"
                  "• **Server Backup & Restore** capabilities",
            inline=False
        )
        
        welcome_embed.add_field(
            name="⚡ Quick Start",
            value="Server admins can run `!setup` to automatically configure all security features!",
            inline=False
        )
        
        welcome_embed.set_footer(text="AegisGuard | Enterprise Discord Security")
        
        members_messaged = 0
        max_welcome_dms = 10  # Limit to prevent being flagged as spam
        
        for member in guild.members:
            if member.bot or member == guild.owner:
                continue
            
            if members_messaged >= max_welcome_dms:
                break
            
            try:
                await member.send(embed=welcome_embed)
                members_messaged += 1
                logger.info(f'Sent welcome DM to {member} in {guild.name}')
                
                # Small delay to prevent rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                # User has DMs disabled or other error
                logger.debug(f'Failed to send DM to {member}: {e}')
        
        logger.info(f'Sent welcome DMs to {members_messaged} members in {guild.name}')
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have the required permissions to execute this command.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param}")
        else:
            logger.error(f"Unhandled error: {error}")
            await ctx.send("❌ An unexpected error occurred.")

def main():
    """Main function to run the bot"""
    # Get bot token from environment variable
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        logger.error("DISCORD_BOT_TOKEN environment variable not set!")
        return
    
    # Create bot instance
    bot = SecurityBot()
    
    # Add basic help command
    @bot.tree.command(name="help", description="Shows available commands")
    async def help_command(interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ AegisGuard Commands",
            description="Comprehensive security and moderation commands:",
            color=0x3498db
        )
        
        embed.add_field(
            name="**🔨 Moderation Commands**",
            value="`/kick` `/ban` `/mute` `/unmute`\n"
                  "`/warn` `/warnings` `/purge` `/nuke`\n"
                  "`/massban` `/masskick`",
            inline=True
        )
        
        embed.add_field(
            name="**🛡️ Security Commands**",
            value="`/lockdown` `/unlock` `/antiraid`\n"
                  "`/quarantine` `/unquarantine`\n"
                  "`/antinuke` `/panic` `/immune`\n"
                  "`/verification` `/verify`\n"
                  "`/automod` `/automod_status`",
            inline=True
        )
        
        embed.add_field(
            name="**📊 Utility Commands**",
            value="`/status` `/ping` `/about` `/logs`\n"
                  "`/info` `/avatar` `/cases`\n"
                  "`/slowmode` `/lock` `/unlock`\n"
                  "`/backup` `/setup` `/help`",
            inline=True
        )
        
        embed.set_footer(text="AegisGuard | Enterprise Security Protection")
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="status", description="Shows bot status and uptime")
    async def status_command(interaction: discord.Interaction):
        uptime = datetime.utcnow() - bot.start_time
        
        embed = discord.Embed(
            title="🤖 Bot Status",
            color=0x2ecc71
        )
        
        embed.add_field(name="Status", value="🟢 Online", inline=True)
        embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="Guilds", value=len(bot.guilds), inline=True)
        embed.add_field(name="Uptime", value=str(uptime).split('.')[0], inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="ping", description="Check bot latency")
    async def ping_command(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")
    
    @bot.tree.command(name="about", description="Information about the bot and its owner")
    async def about_command(interaction: discord.Interaction):
        # Get bot owner information
        app_info = await bot.application_info()
        owner = app_info.owner
        
        embed = discord.Embed(
            title="🛡️ AegisGuard - Discord Security Bot",
            description="A comprehensive Discord moderation and security bot designed to keep your server safe.",
            color=0x3498db
        )
        
        # Bot information
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"**Servers:** {len(bot.guilds)}\n"
                  f"**Uptime:** {str(datetime.utcnow() - bot.start_time).split('.')[0]}\n"
                  f"**Latency:** {round(bot.latency * 1000)}ms",
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
        
        # Version and links
        embed.add_field(
            name="🔗 Information",
            value="**Version:** 1.0.0\n"
                  "**Library:** discord.py\n"
                  "**Language:** Python",
            inline=True
        )
        
        embed.add_field(
            name="📝 Commands",
            value="Use `/help` to see all available commands",
            inline=True
        )
        
        embed.set_thumbnail(url=bot.user.avatar.url if bot.user and bot.user.avatar else None)
        embed.set_footer(
            text=f"AegisGuard • Keeping your server secure",
            icon_url=bot.user.avatar.url if bot.user and bot.user.avatar else None
        )
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    # Run the bot
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()
