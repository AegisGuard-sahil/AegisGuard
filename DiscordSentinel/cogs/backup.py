import discord
from discord.ext import commands
import json
import asyncio
from datetime import datetime
from utils.database import Database
from utils.permissions import has_permission

class BackupCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
    async def create_backup(self, guild: discord.Guild) -> dict:
        """Create a comprehensive server backup"""
        backup_data = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "timestamp": datetime.utcnow().isoformat(),
            "channels": [],
            "roles": [],
            "categories": [],
            "permissions": {}
        }
        
        try:
            # Backup categories
            for category in guild.categories:
                category_data = {
                    "id": category.id,
                    "name": category.name,
                    "position": category.position,
                    "overwrites": {}
                }
                
                # Store permission overwrites
                for target, overwrite in category.overwrites.items():
                    if isinstance(target, discord.Role):
                        category_data["overwrites"][f"role_{target.id}"] = {
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        }
                    elif isinstance(target, discord.Member):
                        category_data["overwrites"][f"member_{target.id}"] = {
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        }
                
                backup_data["categories"].append(category_data)
            
            # Backup channels
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    channel_data = {
                        "id": channel.id,
                        "name": channel.name,
                        "type": "text",
                        "position": channel.position,
                        "topic": channel.topic,
                        "slowmode_delay": channel.slowmode_delay,
                        "nsfw": channel.nsfw,
                        "category_id": channel.category.id if channel.category else None,
                        "overwrites": {}
                    }
                    
                elif isinstance(channel, discord.VoiceChannel):
                    channel_data = {
                        "id": channel.id,
                        "name": channel.name,
                        "type": "voice",
                        "position": channel.position,
                        "bitrate": channel.bitrate,
                        "user_limit": channel.user_limit,
                        "category_id": channel.category.id if channel.category else None,
                        "overwrites": {}
                    }
                else:
                    continue
                
                # Store permission overwrites
                for target, overwrite in channel.overwrites.items():
                    if isinstance(target, discord.Role):
                        channel_data["overwrites"][f"role_{target.id}"] = {
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        }
                    elif isinstance(target, discord.Member):
                        channel_data["overwrites"][f"member_{target.id}"] = {
                            "allow": overwrite.pair()[0].value,
                            "deny": overwrite.pair()[1].value
                        }
                
                backup_data["channels"].append(channel_data)
            
            # Backup roles (excluding @everyone and bot roles)
            for role in guild.roles:
                if role == guild.default_role or role.managed:
                    continue
                
                role_data = {
                    "id": role.id,
                    "name": role.name,
                    "color": role.color.value,
                    "hoist": role.hoist,
                    "mentionable": role.mentionable,
                    "position": role.position,
                    "permissions": role.permissions.value
                }
                
                backup_data["roles"].append(role_data)
            
            return backup_data
            
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    async def restore_backup(self, guild: discord.Guild, backup_data: dict, partial: bool = False) -> dict:
        """Restore server from backup"""
        results = {
            "categories_restored": 0,
            "channels_restored": 0,
            "roles_restored": 0,
            "errors": []
        }
        
        try:
            # Create role mapping (old_id -> new_role)
            role_mapping = {}
            
            # Restore roles first
            for role_data in backup_data.get("roles", []):
                try:
                    # Check if role already exists
                    existing_role = discord.utils.get(guild.roles, name=role_data["name"])
                    if existing_role and not partial:
                        continue
                    
                    new_role = await guild.create_role(
                        name=role_data["name"],
                        color=discord.Color(role_data["color"]),
                        hoist=role_data["hoist"],
                        mentionable=role_data["mentionable"],
                        permissions=discord.Permissions(role_data["permissions"]),
                        reason="Backup restoration"
                    )
                    
                    role_mapping[role_data["id"]] = new_role
                    results["roles_restored"] += 1
                    
                    # Rate limit
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    results["errors"].append(f"Role '{role_data['name']}': {str(e)}")
            
            # Create category mapping
            category_mapping = {}
            
            # Restore categories
            for category_data in backup_data.get("categories", []):
                try:
                    existing_category = discord.utils.get(guild.categories, name=category_data["name"])
                    if existing_category and not partial:
                        category_mapping[category_data["id"]] = existing_category
                        continue
                    
                    new_category = await guild.create_category(
                        name=category_data["name"],
                        reason="Backup restoration"
                    )
                    
                    category_mapping[category_data["id"]] = new_category
                    results["categories_restored"] += 1
                    
                    # Restore overwrites
                    for target_str, overwrite_data in category_data.get("overwrites", {}).items():
                        try:
                            if target_str.startswith("role_"):
                                role_id = int(target_str.split("_")[1])
                                if role_id in role_mapping:
                                    target_role = role_mapping[role_id]
                                    allow = discord.Permissions(overwrite_data["allow"])
                                    deny = discord.Permissions(overwrite_data["deny"])
                                    overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                                    await new_category.set_permissions(target_role, overwrite=overwrite)
                        except:
                            continue
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    results["errors"].append(f"Category '{category_data['name']}': {str(e)}")
            
            # Restore channels
            for channel_data in backup_data.get("channels", []):
                try:
                    if channel_data["type"] == "text":
                        existing_channel = discord.utils.get(guild.text_channels, name=channel_data["name"])
                        if existing_channel and not partial:
                            continue
                        
                        category = None
                        if channel_data.get("category_id") and channel_data["category_id"] in category_mapping:
                            category = category_mapping[channel_data["category_id"]]
                        
                        new_channel = await guild.create_text_channel(
                            name=channel_data["name"],
                            category=category,
                            topic=channel_data.get("topic"),
                            slowmode_delay=channel_data.get("slowmode_delay", 0),
                            nsfw=channel_data.get("nsfw", False),
                            reason="Backup restoration"
                        )
                        
                    elif channel_data["type"] == "voice":
                        existing_channel = discord.utils.get(guild.voice_channels, name=channel_data["name"])
                        if existing_channel and not partial:
                            continue
                        
                        category = None
                        if channel_data.get("category_id") and channel_data["category_id"] in category_mapping:
                            category = category_mapping[channel_data["category_id"]]
                        
                        new_channel = await guild.create_voice_channel(
                            name=channel_data["name"],
                            category=category,
                            bitrate=min(channel_data.get("bitrate", 64000), guild.bitrate_limit),
                            user_limit=channel_data.get("user_limit", 0),
                            reason="Backup restoration"
                        )
                    else:
                        continue
                    
                    # Restore overwrites
                    for target_str, overwrite_data in channel_data.get("overwrites", {}).items():
                        try:
                            if target_str.startswith("role_"):
                                role_id = int(target_str.split("_")[1])
                                if role_id in role_mapping:
                                    target_role = role_mapping[role_id]
                                    allow = discord.Permissions(overwrite_data["allow"])
                                    deny = discord.Permissions(overwrite_data["deny"])
                                    overwrite = discord.PermissionOverwrite.from_pair(allow, deny)
                                    await new_channel.set_permissions(target_role, overwrite=overwrite)
                        except:
                            continue
                    
                    results["channels_restored"] += 1
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    results["errors"].append(f"Channel '{channel_data['name']}': {str(e)}")
            
            return results
            
        except Exception as e:
            results["errors"].append(f"General error: {str(e)}")
            return results
    
    @discord.app_commands.command(name="backup", description="Create or restore server backups")
    @discord.app_commands.describe(
        action="Create a new backup or restore from existing",
        backup_id="Backup ID to restore (for restore only)"
    )
    @discord.app_commands.choices(action=[
        discord.app_commands.Choice(name="Create Backup", value="create"),
        discord.app_commands.Choice(name="Restore Backup", value="restore"),
        discord.app_commands.Choice(name="List Backups", value="list")
    ])
    async def backup_command(self, interaction: discord.Interaction, action: str, backup_id: str = None):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to manage backups.", ephemeral=True)
            return
        
        if action == "create":
            await interaction.response.defer()
            
            embed = discord.Embed(
                title="💾 Creating Backup",
                description="Creating comprehensive server backup...",
                color=0xf39c12
            )
            
            status_msg = await interaction.followup.send(embed=embed)
            
            backup_data = await self.create_backup(interaction.guild)
            
            if backup_data:
                # Store backup in database
                backup_id = self.db.store_backup(backup_data)
                
                embed = discord.Embed(
                    title="✅ Backup Created",
                    description=f"Server backup created successfully!",
                    color=0x2ecc71
                )
                
                embed.add_field(name="Backup ID", value=f"`{backup_id}`", inline=True)
                embed.add_field(name="Channels", value=len(backup_data["channels"]), inline=True)
                embed.add_field(name="Roles", value=len(backup_data["roles"]), inline=True)
                embed.add_field(name="Categories", value=len(backup_data["categories"]), inline=True)
                embed.add_field(name="Created", value=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), inline=True)
                
                embed.add_field(
                    name="📋 Usage",
                    value=f"Use `/backup restore backup_id:{backup_id}` to restore this backup",
                    inline=False
                )
                
                await status_msg.edit(embed=embed)
                
                # Log action
                self.db.log_action("backup_create", interaction.user.id, None, f"Backup {backup_id} created")
            else:
                embed = discord.Embed(
                    title="❌ Backup Failed",
                    description="Failed to create server backup. Check bot permissions.",
                    color=0xe74c3c
                )
                await status_msg.edit(embed=embed)
        
        elif action == "restore":
            if not backup_id:
                await interaction.response.send_message("❌ You must provide a backup ID to restore.", ephemeral=True)
                return
            
            # Get backup data
            backup_data = self.db.get_backup(backup_id)
            if not backup_data:
                await interaction.response.send_message("❌ Backup not found.", ephemeral=True)
                return
            
            # Confirm restoration
            embed = discord.Embed(
                title="⚠️ Confirm Backup Restoration",
                description="**WARNING:** This will restore channels, roles, and permissions from the backup. "
                           "This action cannot be undone!",
                color=0xf39c12
            )
            
            embed.add_field(name="Backup Date", value=backup_data["timestamp"][:19], inline=True)
            embed.add_field(name="Original Server", value=backup_data["guild_name"], inline=True)
            embed.add_field(name="Items", value=f"{len(backup_data['channels'])} channels, {len(backup_data['roles'])} roles", inline=True)
            
            view = BackupConfirmView(self, backup_data)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        elif action == "list":
            backups = self.db.get_backups(interaction.guild.id)
            
            if not backups:
                embed = discord.Embed(
                    title="💾 Server Backups",
                    description="No backups found for this server.",
                    color=0x95a5a6
                )
                await interaction.response.send_message(embed=embed)
                return
            
            embed = discord.Embed(
                title="💾 Server Backups",
                description=f"Found {len(backups)} backup(s) for this server",
                color=0x3498db
            )
            
            for backup in backups[:10]:  # Show max 10
                timestamp = backup["timestamp"][:19]
                embed.add_field(
                    name=f"📁 Backup {backup['id']}",
                    value=f"**Date:** {timestamp}\n"
                          f"**Items:** {len(backup['channels'])} channels, {len(backup['roles'])} roles",
                    inline=True
                )
            
            if len(backups) > 10:
                embed.set_footer(text=f"Showing 10 of {len(backups)} backups")
            
            await interaction.response.send_message(embed=embed)

class BackupConfirmView(discord.ui.View):
    def __init__(self, cog, backup_data):
        super().__init__(timeout=60)
        self.cog = cog
        self.backup_data = backup_data
    
    @discord.ui.button(label="Confirm Restore", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔄 Restoring Backup",
            description="Restoring server from backup. This may take several minutes...",
            color=0xf39c12
        )
        
        await interaction.edit_original_response(embed=embed, view=None)
        
        results = await self.cog.restore_backup(interaction.guild, self.backup_data)
        
        embed = discord.Embed(
            title="✅ Backup Restored" if not results["errors"] else "⚠️ Backup Partially Restored",
            color=0x2ecc71 if not results["errors"] else 0xf39c12
        )
        
        embed.add_field(name="Categories Restored", value=results["categories_restored"], inline=True)
        embed.add_field(name="Channels Restored", value=results["channels_restored"], inline=True)
        embed.add_field(name="Roles Restored", value=results["roles_restored"], inline=True)
        
        if results["errors"]:
            error_text = "\n".join(results["errors"][:5])
            if len(results["errors"]) > 5:
                error_text += f"\n... and {len(results['errors']) - 5} more errors"
            
            embed.add_field(
                name="⚠️ Errors",
                value=f"```{error_text}```",
                inline=False
            )
        
        await interaction.edit_original_response(embed=embed)
        
        # Log action
        self.cog.db.log_action("backup_restore", interaction.user.id, None, f"Backup restored: {results}")
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_restore(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Restoration Cancelled",
            description="Backup restoration has been cancelled.",
            color=0x95a5a6
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

async def setup(bot):
    await bot.add_cog(BackupCog(bot))