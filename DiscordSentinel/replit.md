# AegisGuard - Discord Security Bot

## Overview

AegisGuard is a comprehensive Discord security bot built with Python and discord.py that provides enterprise-grade protection for Discord servers. The bot features advanced anti-raid protection, quarantine systems, anti-nuke monitoring, mass moderation tools, auto-moderation capabilities, and professional security management features. It's designed to be a complete security solution for Discord servers of all sizes.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Bot Framework
- **Discord.py Library**: Uses the discord.py library with proper intents configuration for message content, members, and guilds
- **Cog-based Architecture**: Modular design with separate cogs for different functionalities (moderation, automod, logging)
- **Command System**: Hybrid approach supporting both slash commands and traditional prefix commands
- **Event-driven Design**: Leverages Discord.py's event system for real-time monitoring and response

### Auto-Moderation System
- **Spam Detection**: Time-window based spam detection using in-memory tracking with configurable thresholds
- **Content Filtering**: Pattern-based detection for invite links and excessive capital letters
- **Rate Limiting**: Built-in rate limiting for auto-moderation actions to prevent abuse
- **Configurable Actions**: Flexible action system supporting warn, mute, kick, and ban responses

### Permission Management
- **Role-based Permissions**: Hierarchical permission system with moderator and admin role classifications
- **Immunity System**: Protection for certain roles from moderation actions
- **Owner Override**: Server owners always have full permissions regardless of role configuration
- **Hierarchy Validation**: Enforces Discord's role hierarchy rules for moderation actions

### Data Persistence
- **JSON-based Storage**: File-based storage using JSON files for warnings, logs, and configuration
- **Database Abstraction**: Custom Database class that abstracts file operations and provides type safety
- **Data Integrity**: Automatic file creation and validation to ensure data consistency

### Configuration System
- **Multi-level Configuration**: Global config.json with guild-specific overrides support
- **Runtime Reconfiguration**: Dynamic configuration loading without requiring bot restarts
- **Default Fallbacks**: Comprehensive default configuration to handle missing or corrupted config files

### Logging and Audit Trail
- **Comprehensive Event Logging**: Tracks member joins/leaves, message deletions, and all moderation actions
- **Structured Log Format**: Consistent log entry format with timestamps, action types, and metadata
- **Database Integration**: All actions are stored in the database for historical tracking and analysis

## External Dependencies

### Core Libraries
- **discord.py**: Primary Discord API wrapper for bot functionality
- **asyncio**: Built-in Python library for asynchronous operations
- **datetime**: Built-in Python library for timestamp handling
- **logging**: Built-in Python library for application logging
- **json**: Built-in Python library for configuration and data persistence
- **re**: Built-in Python library for regular expression pattern matching

### File System Dependencies
- **JSON Configuration Files**: Stores bot settings, guild configurations, and permission mappings
- **Data Directory Structure**: Organized file system for logs, warnings, and persistent data storage

### Discord Platform
- **Discord Bot API**: Requires Discord bot token and appropriate permissions
- **Guild Permissions**: Needs kick members, ban members, manage messages, and manage roles permissions
- **Message Content Intent**: Requires privileged intent for message content access

### Runtime Environment
- **Python 3.8+**: Minimum Python version requirement for discord.py compatibility
- **File System Access**: Requires read/write permissions for data directory and configuration files