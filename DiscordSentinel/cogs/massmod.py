import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from utils.database import Database
from utils.permissions import has_permission

class MassModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
    
    @discord.app_commands.command(name="massban", description="Ban multiple users by ID")
    @discord.app_commands.describe(
        user_ids="User IDs separated by spaces or commas",
        reason="Reason for the bans"
    )
    async def massban(self, interaction: discord.Interaction, user_ids: str, reason: str = "Mass ban"):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions for mass ban.", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message("❌ I don't have permission to ban members.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Parse user IDs
        ids = []
        for id_str in user_ids.replace(',', ' ').split():
            try:
                user_id = int(id_str.strip())
                ids.append(user_id)
            except ValueError:
                continue
        
        if not ids:
            await interaction.followup.send("❌ No valid user IDs provided.", ephemeral=True)
            return
        
        if len(ids) > 50:
            await interaction.followup.send("❌ Maximum 50 users can be banned at once.", ephemeral=True)
            return
        
        banned_count = 0
        failed_count = 0
        
        embed = discord.Embed(
            title="⚡ Mass Ban in Progress",
            description=f"Processing {len(ids)} users...",
            color=0xf39c12
        )
        
        status_msg = await interaction.followup.send(embed=embed)
        
        for user_id in ids:
            try:
                # Check if user is in guild
                member = interaction.guild.get_member(user_id)
                if member:
                    # Check if we can ban this member
                    if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                        failed_count += 1
                        continue
                
                # Perform ban
                await interaction.guild.ban(
                    discord.Object(id=user_id),
                    reason=f"Mass ban by {interaction.user} | {reason}",
                    delete_message_days=1
                )
                
                banned_count += 1
                self.db.log_action("mass_ban", interaction.user.id, user_id, reason)
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except discord.NotFound:
                failed_count += 1
            except discord.Forbidden:
                failed_count += 1
            except Exception:
                failed_count += 1
        
        # Final results
        result_embed = discord.Embed(
            title="✅ Mass Ban Complete",
            color=0x2ecc71 if banned_count > 0 else 0xe74c3c
        )
        
        result_embed.add_field(name="Successfully Banned", value=str(banned_count), inline=True)
        result_embed.add_field(name="Failed", value=str(failed_count), inline=True)
        result_embed.add_field(name="Reason", value=reason, inline=False)
        result_embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        
        await status_msg.edit(embed=result_embed)
    
    @discord.app_commands.command(name="masskick", description="Kick multiple users by ID")
    @discord.app_commands.describe(
        user_ids="User IDs separated by spaces or commas",
        reason="Reason for the kicks"
    )
    async def masskick(self, interaction: discord.Interaction, user_ids: str, reason: str = "Mass kick"):
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions for mass kick.", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message("❌ I don't have permission to kick members.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Parse user IDs
        ids = []
        for id_str in user_ids.replace(',', ' ').split():
            try:
                user_id = int(id_str.strip())
                ids.append(user_id)
            except ValueError:
                continue
        
        if not ids:
            await interaction.followup.send("❌ No valid user IDs provided.", ephemeral=True)
            return
        
        if len(ids) > 50:
            await interaction.followup.send("❌ Maximum 50 users can be kicked at once.", ephemeral=True)
            return
        
        kicked_count = 0
        failed_count = 0
        
        embed = discord.Embed(
            title="⚡ Mass Kick in Progress",
            description=f"Processing {len(ids)} users...",
            color=0xf39c12
        )
        
        status_msg = await interaction.followup.send(embed=embed)
        
        for user_id in ids:
            try:
                member = interaction.guild.get_member(user_id)
                if not member:
                    failed_count += 1
                    continue
                
                # Check hierarchy
                if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                    failed_count += 1
                    continue
                
                # Perform kick
                await member.kick(reason=f"Mass kick by {interaction.user} | {reason}")
                
                kicked_count += 1
                self.db.log_action("mass_kick", interaction.user.id, user_id, reason)
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception:
                failed_count += 1
        
        # Final results
        result_embed = discord.Embed(
            title="✅ Mass Kick Complete",
            color=0x2ecc71 if kicked_count > 0 else 0xe74c3c
        )
        
        result_embed.add_field(name="Successfully Kicked", value=str(kicked_count), inline=True)
        result_embed.add_field(name="Failed", value=str(failed_count), inline=True)
        result_embed.add_field(name="Reason", value=reason, inline=False)
        result_embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
        
        await status_msg.edit(embed=result_embed)
    
    @discord.app_commands.command(name="purge", description="Delete multiple messages")
    @discord.app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user",
        reason="Reason for purge"
    )
    async def purge(self, interaction: discord.Interaction, amount: int, user: discord.Member = None, reason: str = "Message purge"):
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to purge messages.", ephemeral=True)
            return
        
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ I don't have permission to manage messages.", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            def check(message):
                if user:
                    return message.author == user
                return True
            
            deleted = await interaction.channel.purge(limit=amount, check=check)
            
            # Log the action
            self.db.log_action(
                "purge", 
                interaction.user.id, 
                user.id if user else None, 
                f"Purged {len(deleted)} messages | {reason}"
            )
            
            embed = discord.Embed(
                title="🗑️ Messages Purged",
                description=f"Successfully deleted {len(deleted)} messages.",
                color=0x2ecc71
            )
            
            if user:
                embed.add_field(name="Target User", value=user.mention, inline=True)
            
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during purge: {str(e)}", ephemeral=True)
    
    @discord.app_commands.command(name="nuke", description="Delete and recreate a channel")
    @discord.app_commands.describe(
        channel="Channel to nuke (current channel if not specified)",
        reason="Reason for nuking the channel"
    )
    async def nuke(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "Channel nuke"):
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to nuke channels.", ephemeral=True)
            return
        
        target_channel = channel or interaction.channel
        
        # Check bot permissions
        if not interaction.guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ I don't have permission to manage channels.", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # Store channel information
            channel_name = target_channel.name
            channel_position = target_channel.position
            channel_category = target_channel.category
            channel_permissions = target_channel.overwrites
            channel_topic = target_channel.topic
            channel_slowmode = target_channel.slowmode_delay
            
            # Delete the channel
            await target_channel.delete(reason=f"Nuke by {interaction.user} | {reason}")
            
            # Recreate the channel
            new_channel = await interaction.guild.create_text_channel(
                name=channel_name,
                category=channel_category,
                position=channel_position,
                topic=channel_topic,
                slowmode_delay=channel_slowmode,
                overwrites=channel_permissions,
                reason=f"Channel nuke recreation | {reason}"
            )
            
            # Log the action
            self.db.log_action("nuke", interaction.user.id, None, f"Nuked #{channel_name} | {reason}")
            
            embed = discord.Embed(
                title="💥 Channel Nuked",
                description=f"Channel has been completely reset.",
                color=0xe74c3c
            )
            embed.add_field(name="Original Channel", value=f"#{channel_name}", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await new_channel.send(embed=embed)
            
            # If we nuked the interaction channel, send followup to new channel
            if target_channel == interaction.channel:
                await new_channel.send("✅ Channel nuke completed successfully!")
            else:
                await interaction.followup.send(f"✅ Channel #{channel_name} has been nuked and recreated.")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during nuke: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MassModerationCog(bot))