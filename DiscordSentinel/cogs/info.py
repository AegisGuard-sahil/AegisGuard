import discord
from discord.ext import commands
from datetime import datetime
from utils.database import Database
from utils.permissions import has_permission, get_permission_level

class InfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    def get_user_flags(self, user: discord.Member) -> list:
        """Get AegisGuard-style user flags"""
        flags = []
        
        # Permission-based flags
        perm_level = get_permission_level(user)
        if perm_level == "owner":
            flags.append("👑 Server Owner")
        elif perm_level == "admin":
            flags.append("⚡ Administrator")
        elif perm_level == "moderator":
            flags.append("🛡️ Moderator")
        
        # Account age flags
        account_age = (datetime.utcnow() - user.created_at).days
        if account_age < 7:
            flags.append("🆕 New Account")
        elif account_age < 30:
            flags.append("⚠️ Young Account")
        
        # Join age flags
        if user.joined_at:
            join_age = (datetime.utcnow() - user.joined_at).days
            if join_age < 1:
                flags.append("🌟 New Member")
            elif join_age < 7:
                flags.append("📅 Recent Joiner")
        
        # Avatar flags
        if not user.avatar:
            flags.append("❌ No Avatar")
        elif user.avatar.is_animated():
            flags.append("✨ Animated Avatar")
        
        # Bot flags
        if user.bot:
            flags.append("🤖 Bot Account")
            if user.public_flags.verified_bot:
                flags.append("✅ Verified Bot")
        
        # Nitro flags
        if user.premium_since:
            flags.append("💎 Server Booster")
        
        # Role flags
        if len(user.roles) > 10:
            flags.append("🎭 Many Roles")
        
        # Check if quarantined
        quarantine_data = self.db.get_quarantine(user.id, user.guild.id)
        if quarantine_data:
            flags.append("🔒 Quarantined")
        
        # Check warning count
        warning_count = self.db.get_warning_count(user.id)
        if warning_count > 0:
            flags.append(f"⚠️ {warning_count} Warning(s)")
        
        return flags
    
    def analyze_role_danger(self, role: discord.Role) -> tuple:
        """Analyze role danger level like AegisGuard"""
        danger_level = "Safe"
        danger_color = 0x2ecc71
        dangerous_perms = []
        
        perms = role.permissions
        
        # Critical permissions
        if perms.administrator:
            dangerous_perms.append("Administrator")
            danger_level = "CRITICAL"
            danger_color = 0xff0000
        
        # High-risk permissions
        high_risk = [
            (perms.manage_guild, "Manage Server"),
            (perms.manage_roles, "Manage Roles"),
            (perms.manage_channels, "Manage Channels"),
            (perms.manage_webhooks, "Manage Webhooks"),
            (perms.ban_members, "Ban Members"),
            (perms.kick_members, "Kick Members"),
            (perms.manage_messages, "Manage Messages")
        ]
        
        for has_perm, perm_name in high_risk:
            if has_perm:
                dangerous_perms.append(perm_name)
                if danger_level == "Safe":
                    danger_level = "HIGH"
                    danger_color = 0xf39c12
        
        # Medium-risk permissions
        medium_risk = [
            (perms.mute_members, "Mute Members"),
            (perms.deafen_members, "Deafen Members"),
            (perms.move_members, "Move Members"),
            (perms.manage_nicknames, "Manage Nicknames")
        ]
        
        for has_perm, perm_name in medium_risk:
            if has_perm:
                dangerous_perms.append(perm_name)
                if danger_level == "Safe":
                    danger_level = "MEDIUM"
                    danger_color = 0xf1c40f
        
        return danger_level, danger_color, dangerous_perms
    
    @discord.app_commands.command(name="info", description="Get detailed information about users, roles, or server")
    @discord.app_commands.describe(
        target="User, role, or 'server' to get info about"
    )
    async def info_command(self, interaction: discord.Interaction, target: str = None):
        if not target:
            # Default to user who ran command
            await self.show_user_info(interaction, interaction.user)
            return
        
        # Check if target is "server"
        if target.lower() == "server":
            await self.show_server_info(interaction)
            return
        
        # Try to parse as user mention or ID
        try:
            if target.startswith("<@") and target.endswith(">"):
                user_id = int(target[2:-1].replace("!", ""))
            else:
                user_id = int(target)
            
            user = interaction.guild.get_member(user_id)
            if user:
                await self.show_user_info(interaction, user)
                return
        except ValueError:
            pass
        
        # Try to find by username
        user = discord.utils.get(interaction.guild.members, name=target)
        if user:
            await self.show_user_info(interaction, user)
            return
        
        # Try to parse as role mention or find by name
        try:
            if target.startswith("<@&") and target.endswith(">"):
                role_id = int(target[3:-1])
                role = interaction.guild.get_role(role_id)
            else:
                role = discord.utils.get(interaction.guild.roles, name=target)
            
            if role:
                await self.show_role_info(interaction, role)
                return
        except ValueError:
            pass
        
        await interaction.response.send_message("❌ User, role, or 'server' not found.", ephemeral=True)
    
    async def show_user_info(self, interaction: discord.Interaction, user: discord.Member):
        """Show detailed user information"""
        embed = discord.Embed(
            title=f"👤 User Information",
            color=user.color if user.color != discord.Color.default() else 0x3498db
        )
        
        # Basic info
        embed.add_field(
            name="📝 Basic Info",
            value=f"**Name:** {user.name}\n"
                  f"**Display Name:** {user.display_name}\n"
                  f"**ID:** `{user.id}`\n"
                  f"**Mention:** {user.mention}",
            inline=True
        )
        
        # Dates
        account_age = (datetime.utcnow() - user.created_at).days
        join_age = (datetime.utcnow() - user.joined_at).days if user.joined_at else 0
        
        embed.add_field(
            name="📅 Dates",
            value=f"**Created:** {user.created_at.strftime('%Y-%m-%d')}\n"
                  f"**Joined:** {user.joined_at.strftime('%Y-%m-%d') if user.joined_at else 'Unknown'}\n"
                  f"**Account Age:** {account_age} days\n"
                  f"**Member For:** {join_age} days",
            inline=True
        )
        
        # Status
        status_emoji = {
            discord.Status.online: "🟢",
            discord.Status.idle: "🟡",
            discord.Status.dnd: "🔴",
            discord.Status.offline: "⚫"
        }
        
        embed.add_field(
            name="📊 Status",
            value=f"**Status:** {status_emoji.get(user.status, '❓')} {user.status}\n"
                  f"**Top Role:** {user.top_role.mention}\n"
                  f"**Role Count:** {len(user.roles) - 1}\n"
                  f"**Boosting:** {'Yes' if user.premium_since else 'No'}",
            inline=True
        )
        
        # Flags
        flags = self.get_user_flags(user)
        if flags:
            embed.add_field(
                name="🏷️ Flags",
                value="\n".join(flags[:10]),  # Show max 10 flags
                inline=False
            )
        
        # Moderation history
        warning_count = self.db.get_warning_count(user.id)
        recent_actions = self.db.get_recent_logs(5, user.id)
        
        if warning_count > 0 or recent_actions:
            mod_text = f"**Warnings:** {warning_count}\n"
            if recent_actions:
                mod_text += f"**Recent Actions:** {len(recent_actions)}"
            
            embed.add_field(
                name="⚖️ Moderation",
                value=mod_text,
                inline=True
            )
        
        # Set avatar
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    async def show_role_info(self, interaction: discord.Interaction, role: discord.Role):
        """Show detailed role information with danger analysis"""
        danger_level, danger_color, dangerous_perms = self.analyze_role_danger(role)
        
        embed = discord.Embed(
            title=f"🎭 Role Information",
            color=danger_color
        )
        
        # Basic info
        embed.add_field(
            name="📝 Basic Info",
            value=f"**Name:** {role.name}\n"
                  f"**ID:** `{role.id}`\n"
                  f"**Mention:** {role.mention}\n"
                  f"**Color:** {str(role.color)}",
            inline=True
        )
        
        # Settings
        embed.add_field(
            name="⚙️ Settings",
            value=f"**Position:** {role.position}\n"
                  f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
                  f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n"
                  f"**Members:** {len(role.members)}",
            inline=True
        )
        
        # Danger analysis
        danger_emoji = {
            "Safe": "✅",
            "MEDIUM": "⚠️",
            "HIGH": "🚨",
            "CRITICAL": "💀"
        }
        
        embed.add_field(
            name="🛡️ Security Analysis",
            value=f"**Danger Level:** {danger_emoji.get(danger_level, '❓')} {danger_level}\n"
                  f"**Created:** {role.created_at.strftime('%Y-%m-%d')}",
            inline=True
        )
        
        # Dangerous permissions
        if dangerous_perms:
            perms_text = "\n".join([f"• {perm}" for perm in dangerous_perms[:10]])
            if len(dangerous_perms) > 10:
                perms_text += f"\n... and {len(dangerous_perms) - 10} more"
            
            embed.add_field(
                name="⚠️ Dangerous Permissions",
                value=perms_text,
                inline=False
            )
        
        # Members with role (if manageable list)
        if len(role.members) <= 20 and len(role.members) > 0:
            members_text = "\n".join([f"• {member.name}" for member in role.members[:10]])
            if len(role.members) > 10:
                members_text += f"\n... and {len(role.members) - 10} more"
            
            embed.add_field(
                name="👥 Members",
                value=members_text,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    async def show_server_info(self, interaction: discord.Interaction):
        """Show detailed server information with security status"""
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"🏰 Server Information",
            color=0x3498db
        )
        
        # Basic info
        embed.add_field(
            name="📝 Basic Info",
            value=f"**Name:** {guild.name}\n"
                  f"**ID:** `{guild.id}`\n"
                  f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                  f"**Created:** {guild.created_at.strftime('%Y-%m-%d')}",
            inline=True
        )
        
        # Statistics
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed.add_field(
            name="📊 Statistics",
            value=f"**Members:** {guild.member_count}\n"
                  f"**Roles:** {len(guild.roles)}\n"
                  f"**Text Channels:** {text_channels}\n"
                  f"**Voice Channels:** {voice_channels}",
            inline=True
        )
        
        # Features
        features = []
        if guild.premium_tier > 0:
            features.append(f"💎 Boost Level {guild.premium_tier}")
        if guild.verification_level != discord.VerificationLevel.none:
            features.append(f"🛡️ Verification: {guild.verification_level.name.title()}")
        if guild.explicit_content_filter != discord.ContentFilter.disabled:
            features.append(f"🔞 Content Filter: {guild.explicit_content_filter.name.title()}")
        
        if features:
            embed.add_field(
                name="✨ Features",
                value="\n".join(features),
                inline=True
            )
        
        # Security status
        antinuke_cog = self.bot.get_cog('AntiNukeCog')
        antiraid_cog = self.bot.get_cog('AntiRaidCog')
        verification_cog = self.bot.get_cog('VerificationCog')
        
        security_status = []
        if antinuke_cog and antinuke_cog.antinuke_enabled:
            security_status.append("🛡️ Anti-Nuke Active")
        if antiraid_cog and antiraid_cog.raid_protection_enabled:
            security_status.append("🚨 Anti-Raid Active")
        if verification_cog and verification_cog.verification_enabled:
            security_status.append("✅ Verification Active")
        
        if security_status:
            embed.add_field(
                name="🔒 Security Status",
                value="\n".join(security_status),
                inline=False
            )
        
        # Set server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="avatar", description="Display a user's avatar")
    @discord.app_commands.describe(user="User to show avatar for")
    async def avatar_command(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {target.name}'s Avatar",
            color=target.color if target.color != discord.Color.default() else 0x3498db
        )
        
        if target.avatar:
            embed.set_image(url=target.avatar.url)
            embed.add_field(
                name="🔗 Links",
                value=f"[PNG]({target.avatar.replace(format='png', size=1024)}) | "
                      f"[JPG]({target.avatar.replace(format='jpg', size=1024)}) | "
                      f"[WEBP]({target.avatar.replace(format='webp', size=1024)})",
                inline=False
            )
            
            if target.avatar.is_animated():
                embed.add_field(
                    name="✨ Animated",
                    value=f"[GIF]({target.avatar.replace(format='gif', size=1024)})",
                    inline=True
                )
        else:
            embed.description = "This user has no custom avatar."
            embed.set_image(url=target.default_avatar.url)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(InfoCog(bot))