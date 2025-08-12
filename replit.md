# Overview

This is a Discord Leaderboard Bot that tracks user activity across message sending and voice channel participation. The bot maintains real-time leaderboards showing the most active users in a Discord server, with separate tracking for messages sent and time spent in voice channels. The system is designed with performance optimization, caching, and robust error handling to support high-activity Discord servers.

# User Preferences

Preferred communication style: Simple, everyday language.
Discord configuration: Target guild ID 1315029949211738222, message leaderboard channel ID 1404855785183252572 (chat-lb), voice leaderboard channel ID 1404855743596728374 (vc-lb).
Design preference: Professional aesthetic with custom purple color scheme (#571173), guild icon thumbnails, animated purple arrow emoji (<a:purp_arrow:1403295268505522187>) for ALL top 10 members, bold titles, clean format with proper usernames (not user IDs).
Leaderboard configuration: Limited to top 10 users only, with automatic 30-day refresh cycle to reset all leaderboard data.
Issues resolved: Username display shows actual Discord usernames instead of user IDs, leaderboard limited to top 10, 30-day refresh implemented - all fixed on August 12, 2025.

# System Architecture

## Bot Framework
- **Discord.py Framework**: Uses discord.py with custom bot class `OptimizedLeaderboardBot` extending `commands.Bot`
- **Cog-based Architecture**: Modular command structure using Discord.py cogs for organized functionality
- **Async/Await Pattern**: Full asynchronous operation for handling concurrent Discord events and database operations

## Database Layer
- **SQLite with Connection Pooling**: Thread-safe connection pool managing multiple database connections for concurrent access
- **Batch Operations**: Optimized batch processing for bulk database updates to reduce I/O overhead
- **Data Models**: Structured data classes for user message stats, voice stats, and leaderboard entries
- **Schema**: Three main tables - messages (user_id, count), voice (user_id, total_time, join_time), settings (key-value configuration)

## Caching System
- **In-Memory Cache**: LRU cache with TTL (Time-To-Live) support for frequently accessed leaderboard data
- **Thread-Safe Operations**: RLock-based synchronization for concurrent cache access
- **Automatic Cleanup**: Background task for expired entry removal and memory management
- **Performance Metrics**: Built-in cache hit/miss tracking for optimization monitoring

## Services Architecture
- **LeaderboardService**: Core business logic for tracking user activity and generating leaderboards
- **CacheService**: Centralized caching with configurable TTL and size limits
- **DatabaseManager**: Abstracted database operations with connection pooling and error handling

## Performance Optimization
- **Rate Limiting**: Token bucket algorithm preventing spam and API abuse
- **Background Tasks**: Separate async tasks for periodic updates, cleanup, and maintenance
- **Batch Processing**: Grouped database operations to minimize connection overhead
- **Performance Monitoring**: Built-in metrics collection and system health checks

## Configuration Management
- **Environment Variables**: Flexible configuration through environment variables with sensible defaults
- **Validation**: Input validation for all configuration parameters
- **Hot Configuration**: Runtime configuration updates without restart

## Error Handling & Logging
- **Structured Logging**: JSON-formatted logs with metadata for production monitoring
- **Performance Monitoring**: Real-time system metrics (CPU, memory, response times)
- **Health Checks**: Automated system health verification with status reporting
- **Graceful Degradation**: Fallback mechanisms for service failures

# External Dependencies

## Core Dependencies
- **Discord.py**: Python library for Discord bot API integration
- **SQLite3**: Built-in Python database for persistent storage
- **asyncio**: Python async framework for concurrent operations

## System Monitoring
- **psutil**: System resource monitoring (CPU, memory, disk usage)
- **threading**: Multi-threading support for concurrent operations
- **logging**: Python logging framework with custom formatters

## Discord Integration
- **Discord Bot API**: Real-time message and voice state event handling
- **Discord Intents**: Message content, voice states, guild members, and guild access permissions
- **Discord Webhooks**: For potential notification features

## Development Dependencies
- **dataclasses**: Python data structure definitions
- **typing**: Type hints and annotations for code clarity
- **contextlib**: Context managers for resource management
- **collections**: Specialized data structures (deque, defaultdict, OrderedDict)

## Configuration
- **Environment Variables**: BOT_TOKEN, channel IDs, database path, and performance tuning parameters
- **Default Values**: Fallback configuration for development and testing environments