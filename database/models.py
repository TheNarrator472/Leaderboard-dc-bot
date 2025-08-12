"""
Data models for the leaderboard bot.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class UserMessageStats:
    """User message statistics."""
    user_id: int
    guild_id: int
    channel_id: int
    count: int
    last_updated: datetime
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'UserMessageStats':
        """Create from database row."""
        return cls(
            user_id=row[0],
            guild_id=row[1],
            channel_id=row[2],
            count=row[3],
            last_updated=datetime.fromtimestamp(row[4])
        )


@dataclass
class UserVoiceStats:
    """User voice statistics."""
    user_id: int
    guild_id: int
    total_time: int  # seconds
    join_time: Optional[int]  # timestamp
    last_updated: datetime
    
    @property
    def is_in_voice(self) -> bool:
        """Check if user is currently in voice."""
        return self.join_time is not None
    
    @property
    def current_session_time(self) -> int:
        """Get current session time in seconds."""
        if not self.is_in_voice:
            return 0
        return int(datetime.now().timestamp()) - self.join_time
    
    @property
    def total_time_including_current(self) -> int:
        """Get total time including current session."""
        return self.total_time + self.current_session_time
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'UserVoiceStats':
        """Create from database row."""
        return cls(
            user_id=row[0],
            guild_id=row[1],
            total_time=row[2],
            join_time=row[3],
            last_updated=datetime.fromtimestamp(row[4])
        )


@dataclass
class LeaderboardEntry:
    """Leaderboard entry with user information."""
    position: int
    user_id: int
    username: str
    value: int  # message count or voice time
    formatted_value: str
    
    @classmethod
    def create_message_entry(cls, position: int, user_id: int, username: str, count: int) -> 'LeaderboardEntry':
        """Create message leaderboard entry."""
        return cls(
            position=position,
            user_id=user_id,
            username=username,
            value=count,
            formatted_value=f"{count:,} messages"
        )
    
    @classmethod
    def create_voice_entry(cls, position: int, user_id: int, username: str, total_seconds: int) -> 'LeaderboardEntry':
        """Create voice leaderboard entry."""
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        
        if hours > 0:
            formatted = f"{hours}h {minutes}m"
        else:
            formatted = f"{minutes}m"
        
        return cls(
            position=position,
            user_id=user_id,
            username=username,
            value=total_seconds,
            formatted_value=formatted
        )


@dataclass
class GuildConfig:
    """Guild-specific configuration."""
    guild_id: int
    message_channel_id: Optional[int]
    voice_channel_id: Optional[int]
    enabled_features: list
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_db_row(cls, row: tuple) -> 'GuildConfig':
        """Create from database row."""
        features = row[3].split(',') if row[3] else []
        return cls(
            guild_id=row[0],
            message_channel_id=row[1],
            voice_channel_id=row[2],
            enabled_features=features,
            created_at=datetime.fromtimestamp(row[4]),
            updated_at=datetime.fromtimestamp(row[5])
        )
