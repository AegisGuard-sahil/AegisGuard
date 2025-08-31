import discord
import json
import os

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except:
        # Return default config if file doesn't exist
        return {
            "permissions": {
                "moderator_roles": ["Moderator", "Admin", "Staff"],
                "admin_roles": ["Admin", "Owner"],
                "immune_roles": ["Admin", "Owner", "Bot"]
            }
        }

def has_permission(user: discord.Member | discord.User, permission_level: str) -> bool:
    """Check if a user has the required permission level"""
    if not isinstance(user, (discord.Member, discord.User)):
        return False
    
    # If it's a User object (not Member), we can't check guild permissions
    if isinstance(user, discord.User):
        return False
    
    config = load_config()
    permissions = config.get("permissions", {})
    
    # Server owner always has all permissions
    if user.guild.owner_id == user.id:
        return True
    
    # Check for administrator permission
    if user.guild_permissions.administrator:
        return True
    
    user_roles = [role.name for role in user.roles]
    
    if permission_level == "moderator":
        # Moderators and admins can use moderator commands
        moderator_roles = permissions.get("moderator_roles", [])
        admin_roles = permissions.get("admin_roles", [])
        return any(role in user_roles for role in moderator_roles + admin_roles)
    
    elif permission_level == "admin":
        # Only admins can use admin commands
        admin_roles = permissions.get("admin_roles", [])
        return any(role in user_roles for role in admin_roles)
    
    return False

def is_immune(user: discord.Member | discord.User) -> bool:
    """Check if a user is immune to moderation actions"""
    if not isinstance(user, (discord.Member, discord.User)):
        return False
    
    # If it's a User object (not Member), they're not immune
    if isinstance(user, discord.User):
        return False
    
    config = load_config()
    permissions = config.get("permissions", {})
    
    # Server owner is always immune
    if user.guild.owner_id == user.id:
        return True
    
    # Check for administrator permission
    if user.guild_permissions.administrator:
        return True
    
    # Check immune roles
    immune_roles = permissions.get("immune_roles", [])
    user_roles = [role.name for role in user.roles]
    
    return any(role in user_roles for role in immune_roles)

def get_permission_level(user: discord.Member | discord.User) -> str:
    """Get the highest permission level for a user"""
    if not isinstance(user, (discord.Member, discord.User)):
        return "none"
    
    # If it's a User object (not Member), return basic level
    if isinstance(user, discord.User):
        return "member"
    
    if user.guild.owner_id == user.id:
        return "owner"
    
    if user.guild_permissions.administrator:
        return "admin"
    
    if has_permission(user, "admin"):
        return "admin"
    
    if has_permission(user, "moderator"):
        return "moderator"
    
    return "member"

def can_moderate(moderator: discord.Member | discord.User, target: discord.Member | discord.User) -> bool:
    """Check if a moderator can take action against a target user"""
    if not isinstance(moderator, (discord.Member, discord.User)) or not isinstance(target, (discord.Member, discord.User)):
        return False
    
    # Both must be Members to check moderation permissions
    if not isinstance(moderator, discord.Member) or not isinstance(target, discord.Member):
        return False
    
    # Can't moderate yourself
    if moderator.id == target.id:
        return False
    
    # Check if target is immune
    if is_immune(target):
        return False
    
    # Check if moderator has permission
    if not has_permission(moderator, "moderator"):
        return False
    
    # Check role hierarchy (except for server owner)
    if moderator.guild.owner_id != moderator.id:
        if target.top_role >= moderator.top_role:
            return False
    
    return True

def get_required_permission(command_name: str) -> str:
    """Get the required permission level for a command"""
    admin_commands = [
        "automod",
        "setup",
        "config"
    ]
    
    moderator_commands = [
        "kick", "ban", "mute", "unmute", "warn", "warnings",
        "logs", "automod_status", "clear_warnings"
    ]
    
    if command_name in admin_commands:
        return "admin"
    elif command_name in moderator_commands:
        return "moderator"
    else:
        return "member"
