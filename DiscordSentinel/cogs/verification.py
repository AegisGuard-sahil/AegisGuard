import discord
from discord.ext import commands
import asyncio
import random
import string
from datetime import datetime, timedelta
from utils.database import Database
from utils.permissions import has_permission

class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()
        
        # Verification settings
        self.verification_enabled = False
        self.verification_channel = None
        self.verified_role = None
        self.unverified_role = None
        
        # Pending verifications
        self.pending_verifications = {}
        
        # Verification methods
        self.verification_methods = {
            'reaction': True,
            'captcha': False,
            'button': True
        }
    
    def generate_captcha(self) -> str:
        """Generate a simple captcha code"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member verification"""
        if not self.verification_enabled:
            return
        
        # Add unverified role if configured
        if self.unverified_role:
            try:
                await member.add_roles(self.unverified_role, reason="New member - pending verification")
            except:
                pass
        
        # Send verification message
        if self.verification_channel:
            await self.send_verification_message(member)
    
    async def send_verification_message(self, member: discord.Member):
        """Send verification message to new member"""
        embed = discord.Embed(
            title="🛡️ Server Verification Required",
            description=f"Welcome to **{member.guild.name}**, {member.mention}!",
            color=0x3498db
        )
        
        embed.add_field(
            name="⚠️ Verification Needed",
            value="To access the server, you need to verify that you're human.\n"
                  "This helps protect our community from bots and spam.",
            inline=False
        )
        
        if self.verification_methods['button']:
            embed.add_field(
                name="✅ How to Verify",
                value="Click the **Verify** button below to complete verification.",
                inline=False
            )
            
            view = VerificationView(self)
            
            try:
                await self.verification_channel.send(embed=embed, view=view)
            except:
                pass
        
        elif self.verification_methods['reaction']:
            embed.add_field(
                name="✅ How to Verify",
                value="React with ✅ to verify yourself.",
                inline=False
            )
            
            try:
                msg = await self.verification_channel.send(embed=embed)
                await msg.add_reaction("✅")
                
                # Store message for reaction handling
                self.pending_verifications[msg.id] = member.id
                
            except:
                pass
        
        elif self.verification_methods['captcha']:
            captcha_code = self.generate_captcha()
            self.pending_verifications[member.id] = captcha_code
            
            embed.add_field(
                name="🔤 Captcha Code",
                value=f"Type this code: `{captcha_code}`",
                inline=False
            )
            
            try:
                await self.verification_channel.send(embed=embed)
            except:
                pass
    
    async def verify_member(self, member: discord.Member) -> bool:
        """Verify a member and give them access"""
        try:
            # Remove unverified role
            if self.unverified_role and self.unverified_role in member.roles:
                await member.remove_roles(self.unverified_role, reason="Verification completed")
            
            # Add verified role
            if self.verified_role:
                await member.add_roles(self.verified_role, reason="Verification completed")
            
            # Log verification
            self.db.log_action("verification_success", None, member.id, "Member completed verification")
            
            # Send success message
            embed = discord.Embed(
                title="✅ Verification Complete",
                description=f"Welcome to the server, {member.mention}! You now have full access.",
                color=0x2ecc71
            )
            
            if self.verification_channel:
                await self.verification_channel.send(embed=embed, delete_after=10)
            
            return True
            
        except Exception as e:
            print(f"Error verifying member: {e}")
            return False
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle verification reactions"""
        if user.bot:
            return
        
        # Check if it's a verification reaction
        if reaction.message.id in self.pending_verifications:
            if str(reaction.emoji) == "✅":
                member_id = self.pending_verifications[reaction.message.id]
                if user.id == member_id:
                    await self.verify_member(user)
                    del self.pending_verifications[reaction.message.id]
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle captcha verification"""
        if message.author.bot:
            return
        
        # Check if it's captcha verification
        if message.author.id in self.pending_verifications:
            expected_code = self.pending_verifications[message.author.id]
            if message.content.strip().upper() == expected_code:
                await self.verify_member(message.author)
                del self.pending_verifications[message.author.id]
                
                try:
                    await message.delete()
                except:
                    pass
    
    @discord.app_commands.command(name="verification", description="Configure server verification system")
    @discord.app_commands.describe(
        enabled="Enable or disable verification",
        channel="Channel for verification messages",
        verified_role="Role to give verified members",
        unverified_role="Role for unverified members",
        method="Verification method (reaction/button/captcha)"
    )
    @discord.app_commands.choices(method=[
        discord.app_commands.Choice(name="Reaction", value="reaction"),
        discord.app_commands.Choice(name="Button", value="button"),
        discord.app_commands.Choice(name="Captcha", value="captcha")
    ])
    async def verification_setup(self, interaction: discord.Interaction,
                               enabled: bool = None,
                               channel: discord.TextChannel = None,
                               verified_role: discord.Role = None,
                               unverified_role: discord.Role = None,
                               method: str = None):
        
        if not has_permission(interaction.user, 'admin'):
            await interaction.response.send_message("❌ You need admin permissions to configure verification.", ephemeral=True)
            return
        
        # Update settings
        if enabled is not None:
            self.verification_enabled = enabled
        
        if channel:
            self.verification_channel = channel
        
        if verified_role:
            self.verified_role = verified_role
        
        if unverified_role:
            self.unverified_role = unverified_role
        
        if method:
            # Reset all methods
            for m in self.verification_methods:
                self.verification_methods[m] = False
            self.verification_methods[method] = True
        
        # Show current configuration
        embed = discord.Embed(
            title="🛡️ Verification System Configuration",
            color=0x3498db
        )
        
        status = "🟢 Enabled" if self.verification_enabled else "🔴 Disabled"
        embed.add_field(name="Status", value=status, inline=True)
        
        channel_name = self.verification_channel.mention if self.verification_channel else "Not set"
        embed.add_field(name="Channel", value=channel_name, inline=True)
        
        verified_role_name = self.verified_role.mention if self.verified_role else "Not set"
        embed.add_field(name="Verified Role", value=verified_role_name, inline=True)
        
        unverified_role_name = self.unverified_role.mention if self.unverified_role else "Not set"
        embed.add_field(name="Unverified Role", value=unverified_role_name, inline=True)
        
        active_method = next((method for method, active in self.verification_methods.items() if active), "None")
        embed.add_field(name="Method", value=active_method.title(), inline=True)
        
        pending_count = len(self.pending_verifications)
        embed.add_field(name="Pending Verifications", value=str(pending_count), inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="verify", description="Manually verify a member")
    @discord.app_commands.describe(user="User to verify")
    async def manual_verify(self, interaction: discord.Interaction, user: discord.Member):
        if not has_permission(interaction.user, 'moderator'):
            await interaction.response.send_message("❌ You need moderator permissions to manually verify users.", ephemeral=True)
            return
        
        success = await self.verify_member(user)
        
        if success:
            embed = discord.Embed(
                title="✅ Manual Verification",
                description=f"{user.mention} has been manually verified.",
                color=0x2ecc71
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
            # Log action
            self.db.log_action("manual_verification", interaction.user.id, user.id, "Manual verification by moderator")
        else:
            await interaction.response.send_message("❌ Failed to verify user.", ephemeral=True)

class VerificationView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(label="Verify", style=discord.ButtonStyle.green, emoji="✅")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = interaction.user
        
        success = await self.cog.verify_member(member)
        
        if success:
            await interaction.response.send_message("✅ You have been verified! Welcome to the server.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Verification failed. Please contact a moderator.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(VerificationCog(bot))