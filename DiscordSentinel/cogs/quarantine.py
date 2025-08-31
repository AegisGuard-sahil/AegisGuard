import discord
from discord.ext import commands
from datetime import datetime
from utils.database import Database
from utils.permissions import has_permission, is_immune

class QuarantineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Quarantine tracking
        self.quarantined_users = set()
        
    async def setup_quarantine_role(self, guild: discord.Guild) -> discord.Role:
        """Create or get quarantine role with zero permissions"""
        quarantine_role = discord.utils.get(guild.roles, name="🔒 Quarantined")
        
        if not quarantine_role:
            # Create quarantine role
            try:
                quarantine_role = await guild.create_role(
                    name="🔒 Quarantined",
                    color=discord.Color.dark_red(),
                    permissions=discord.Permissions.none(),
                    reason="Quarantine system setup"
                )
                
                # Set permissions for all channels
                for channel in guild.channels:
                    try:
                        await channel.set_permissions(
                            quarantine_role,
                            view_channel=False,
                            send_messages=False,
                            add_reactions=False,
                            connect=False,
                            speak=False,
                            reason="Quarantine role setup"
                        )
                    except:
                        continue
                        
            except discord.Forbidden:
                return None
        
        return quarantine_role
    
    async def quarantine_user(self, user: discord.Member, moderator: discord.Member, reason: str) -> bool:
        """Put a user in quarantine"""
        try:
            # Get quarantine role
            quarantine_role = await self.setup_quarantine_role(user.guild)
            if not quarantine_role:
                return False
            
            # Store user's original roles
            original_roles = [role.id for role in user.roles if role != user.guild.default_role]
            
            # Remove all roles except @everyone
            try:
                await user.edit(roles=[], reason=f"Quarantine by {moderator} | {reason}")
            except:
                pass
            
            # Add quarantine role
            await user.add_roles(quarantine_role, reason=f"Quarantine by {moderator} | {reason}")
            
            # Store quarantine data
            quarantine_data = {
                "user_id": user.id,
                "guild_id": user.guild.id,
                "moderator_id": moderator.id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                "original_roles": original_roles
            }
            
            self.db.add_quarantine(quarantine_data)
            self.quarantined_users.add(user.id)
            
            # Log action
            self.db.log_action("quarantine", moderator.id, user.id, reason)
            
            # Try to DM user
            try:
                embed = discord.Embed(
                    title="🔒 You have been quarantined",
                    description=f"You were quarantined in **{user.guild.name}**",
                    color=0xe74c3c
                )
                embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(name="Moderator", value=moderator.mention, inline=False)
                embed.add_field(
                    name="What this means",
                    value="You have been isolated and cannot see or interact with any channels. "
                          "Contact a moderator if you believe this was an error.",
                    inline=False
                )
                await user.send(embed=embed)
            except:
                pass
            
            return True
            
        except Exception as e:
            print(f"Error quarantining user: {e}")
            return False
    
    async def unquarantine_user(self, user: discord.Member, moderator: discord.Member, reason: str) -> bool:
        """Remove a user from quarantine"""
        try:
            # Get quarantine data
            quarantine_data = self.db.get_quarantine(user.id, user.guild.id)
            if not quarantine_data:
                return False
            
            # Get quarantine role
            quarantine_role = discord.utils.get(user.guild.roles, name="🔒 Quarantined")
            
            # Remove quarantine role
            if quarantine_role and quarantine_role in user.roles:
                await user.remove_roles(quarantine_role, reason=f"Unquarantine by {moderator} | {reason}")
            
            # Restore original roles
            original_roles = []
            for role_id in quarantine_data.get("original_roles", []):
                role = user.guild.get_role(role_id)
                if role:
                    original_roles.append(role)
            
            if original_roles:
                try:
                    await user.edit(roles=original_roles, reason=f"Restore roles after unquarantine | {reason}")
                except:
                    pass
            
            # Remove from database
            self.db.remove_quarantine(user.id, user.guild.id)
            self.quarantined_users.discard(user.id)
            
            # Log action
            self.db.log_action("unquarantine", moderator.id, user.id, reason)
            
            return True
            
        except Exception as e:
            print(f"Error unquarantining user: {e}")
            return False
    
    @discord.app_commands.command(name="quarantine", description="Quarantine a user (AegisGuard's signature isolation)")
    @discord.app_commands.describe(
        user="User to quarantine",
        reason="Reason for quarantine"
    )
    async def quarantine_command(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to quarantine users.", ephemeral=True)
            return
        
        # Check if user is immune
        if is_immune(user):
            await interaction.response.send_message("❌ Cannot quarantine this user (immune role).", ephemeral=True)
            return
        
        # Check if already quarantined
        if user.id in self.quarantined_users:
            await interaction.response.send_message("❌ User is already quarantined.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        success = await self.quarantine_user(user, interaction.user, reason)
        
        if success:
            embed = discord.Embed(
                title="🔒 User Quarantined",
                description=f"**{user}** has been isolated in quarantine.",
                color=0xe74c3c
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(
                name="⚠️ Quarantine Effects",
                value="• User cannot see any channels\n"
                      "• User cannot send messages\n"
                      "• User cannot join voice channels\n"
                      "• All original roles removed",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to quarantine user. Check bot permissions.", ephemeral=True)
    
    @discord.app_commands.command(name="unquarantine", description="Remove a user from quarantine")
    @discord.app_commands.describe(
        user="User to unquarantine",
        reason="Reason for unquarantine"
    )
    async def unquarantine_command(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
        # Check permissions
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to unquarantine users.", ephemeral=True)
            return
        
        # Check if quarantined
        if user.id not in self.quarantined_users:
            await interaction.response.send_message("❌ User is not quarantined.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        success = await self.unquarantine_user(user, interaction.user, reason)
        
        if success:
            embed = discord.Embed(
                title="🔓 User Unquarantined",
                description=f"**{user}** has been released from quarantine.",
                color=0x2ecc71
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            embed.add_field(
                name="✅ Restoration",
                value="• Original roles restored\n"
                      "• Full server access returned\n"
                      "• Quarantine record removed",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ Failed to unquarantine user.", ephemeral=True)
    
    @discord.app_commands.command(name="quarantined", description="List all quarantined users")
    async def quarantined_list(self, interaction: discord.Interaction):
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You don't have permission to view quarantined users.", ephemeral=True)
            return
        
        quarantined = self.db.get_all_quarantined(interaction.guild.id)
        
        if not quarantined:
            embed = discord.Embed(
                title="🔒 Quarantined Users",
                description="No users are currently quarantined.",
                color=0x2ecc71
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = discord.Embed(
            title="🔒 Quarantined Users",
            description=f"**{len(quarantined)}** users currently quarantined",
            color=0xe74c3c
        )
        
        for data in quarantined[:10]:  # Show max 10
            user = self.bot.get_user(data['user_id'])
            moderator = self.bot.get_user(data['moderator_id'])
            
            user_name = user.name if user else f"ID: {data['user_id']}"
            mod_name = moderator.name if moderator else "Unknown"
            timestamp = data['timestamp'][:10]
            
            embed.add_field(
                name=f"👤 {user_name}",
                value=f"**Reason:** {data['reason'][:50]}{'...' if len(data['reason']) > 50 else ''}\n"
                      f"**Moderator:** {mod_name}\n"
                      f"**Date:** {timestamp}",
                inline=True
            )
        
        if len(quarantined) > 10:
            embed.set_footer(text=f"Showing 10 of {len(quarantined)} quarantined users")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(QuarantineCog(bot))