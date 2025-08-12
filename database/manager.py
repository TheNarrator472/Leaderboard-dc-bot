"""
Optimized database manager with connection pooling, batch operations, and error handling.
"""

import asyncio
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Tuple, Optional, Any, Dict
from queue import Queue
from dataclasses import dataclass

from utils.logger import get_logger


@dataclass
class BatchOperation:
    """Represents a batch database operation."""
    query: str
    params: List[Tuple]
    operation_type: str  # 'insert', 'update', 'delete'


class ConnectionPool:
    """
    SQLite connection pool with thread safety and automatic connection management.
    """
    
    def __init__(self, db_path: str, pool_size: int = 10, timeout: int = 30):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._pool = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False
        self.logger = get_logger("database.pool")
    
    def initialize(self):
        """Initialize the connection pool."""
        with self._lock:
            if self._initialized:
                return
            
            try:
                for _ in range(self.pool_size):
                    conn = self._create_connection()
                    self._pool.put(conn)
                
                self._initialized = True
                self.logger.info(f"Connection pool initialized with {self.pool_size} connections")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize connection pool: {e}")
                raise
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with optimizations."""
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=False
        )
        
        # Apply SQLite optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        return conn
    
    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool."""
        if not self._initialized:
            raise RuntimeError("Connection pool not initialized")
        
        conn = None
        try:
            # Get connection from pool with timeout
            conn = await asyncio.get_event_loop().run_in_executor(
                None, self._pool.get, True, self.timeout
            )
            yield conn
        finally:
            if conn:
                # Return connection to pool
                try:
                    self._pool.put(conn, block=False)
                except:
                    # Pool is full, close the connection
                    conn.close()
    
    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    conn.close()
                except:
                    pass
            self._initialized = False


class DatabaseManager:
    """
    Enhanced database manager with batch operations, caching, and performance monitoring.
    """
    
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool = ConnectionPool(db_path, pool_size)
        self.logger = get_logger("database.manager")
        
        # Batch operation queues
        self._batch_queue = asyncio.Queue()
        self._batch_lock = asyncio.Lock()
        self._batch_task = None
        
        # Performance tracking
        self._operation_stats = {
            'total_operations': 0,
            'batch_operations': 0,
            'individual_operations': 0,
            'total_time': 0.0
        }
    
    async def initialize(self):
        """Initialize database and create tables."""
        try:
            self.pool.initialize()
            await self._create_tables()
            await self._create_indexes()
            
            # Start batch processing task
            self._batch_task = asyncio.create_task(self._process_batch_operations())
            
            self.logger.info("Database manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def _create_tables(self):
        """Create database tables with optimized schema."""
        schema_queries = [
            """CREATE TABLE IF NOT EXISTS messages (
                user_id INTEGER NOT NULL,
                guild_id INTEGER,
                channel_id INTEGER,
                count INTEGER DEFAULT 0,
                last_updated INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS voice (
                user_id INTEGER NOT NULL,
                guild_id INTEGER,
                total_time INTEGER DEFAULT 0,
                join_time INTEGER,
                last_updated INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, guild_id)
            )""",
            
            """CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at INTEGER DEFAULT 0
            )""",
            
            """CREATE TABLE IF NOT EXISTS user_cache (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                discriminator TEXT,
                cached_at INTEGER
            )""",
            
            """CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                message_channel_id INTEGER,
                voice_channel_id INTEGER,
                enabled_features TEXT,
                created_at INTEGER,
                updated_at INTEGER
            )"""
        ]
        
        async with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            for query in schema_queries:
                cursor.execute(query)
            conn.commit()
    
    async def _create_indexes(self):
        """Create database indexes for performance."""
        index_queries = [
            "CREATE INDEX IF NOT EXISTS idx_messages_count ON messages(count DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_guild ON messages(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_time ON voice(total_time DESC)",
            "CREATE INDEX IF NOT EXISTS idx_voice_guild ON voice(guild_id)",
            "CREATE INDEX IF NOT EXISTS idx_voice_join_time ON voice(join_time)",
            "CREATE INDEX IF NOT EXISTS idx_user_cache_username ON user_cache(username)",
        ]
        
        async with self.pool.get_connection() as conn:
            cursor = conn.cursor()
            for query in index_queries:
                try:
                    cursor.execute(query)
                except sqlite3.OperationalError as e:
                    if "already exists" not in str(e):
                        self.logger.warning(f"Failed to create index: {e}")
            conn.commit()
    
    async def _process_batch_operations(self):
        """Process batch operations in background."""
        while True:
            try:
                # Collect operations for batch processing
                operations = []
                deadline = time.time() + 5.0  # 5 second batch window
                
                while time.time() < deadline and len(operations) < 100:
                    try:
                        operation = await asyncio.wait_for(
                            self._batch_queue.get(), timeout=1.0
                        )
                        operations.append(operation)
                    except asyncio.TimeoutError:
                        break
                
                if operations:
                    await self._execute_batch_operations(operations)
                
            except Exception as e:
                self.logger.error(f"Error in batch processing: {e}")
                await asyncio.sleep(1)
    
    async def _execute_batch_operations(self, operations: List[BatchOperation]):
        """Execute a batch of database operations."""
        start_time = time.time()
        
        try:
            async with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                
                # Group operations by type
                grouped_ops = {}
                for op in operations:
                    key = (op.query, op.operation_type)
                    if key not in grouped_ops:
                        grouped_ops[key] = []
                    grouped_ops[key].extend(op.params)
                
                # Execute grouped operations
                for (query, op_type), params_list in grouped_ops.items():
                    if params_list:
                        cursor.executemany(query, params_list)
                
                conn.commit()
                
                self._operation_stats['batch_operations'] += len(operations)
                self._operation_stats['total_operations'] += len(operations)
                
        except Exception as e:
            self.logger.error(f"Batch operation failed: {e}")
            raise
        finally:
            execution_time = time.time() - start_time
            self._operation_stats['total_time'] += execution_time
            
            if len(operations) > 10:  # Log only significant batches
                self.logger.debug(f"Executed batch of {len(operations)} operations in {execution_time:.3f}s")
    
    async def queue_batch_operation(self, query: str, params: List[Tuple], operation_type: str):
        """Queue an operation for batch processing."""
        operation = BatchOperation(query, params, operation_type)
        await self._batch_queue.put(operation)
    
    async def execute_query(self, query: str, params: Tuple = (), fetch_one: bool = False, fetch_all: bool = False) -> Optional[Any]:
        """Execute a single query with connection pooling."""
        start_time = time.time()
        
        try:
            async with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                result = None
                if fetch_one:
                    result = cursor.fetchone()
                elif fetch_all:
                    result = cursor.fetchall()
                
                if not (fetch_one or fetch_all):
                    conn.commit()
                
                self._operation_stats['individual_operations'] += 1
                self._operation_stats['total_operations'] += 1
                
                return result
                
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
        finally:
            execution_time = time.time() - start_time
            self._operation_stats['total_time'] += execution_time
    
    async def execute_many(self, query: str, params_list: List[Tuple]):
        """Execute multiple operations efficiently."""
        start_time = time.time()
        
        try:
            async with self.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                
                self._operation_stats['individual_operations'] += len(params_list)
                self._operation_stats['total_operations'] += len(params_list)
                
        except Exception as e:
            self.logger.error(f"Execute many failed: {e}")
            raise
        finally:
            execution_time = time.time() - start_time
            self._operation_stats['total_time'] += execution_time
    
    # Message tracking methods
    async def increment_message_count(self, user_id: int, guild_id: int, channel_id: int):
        """Increment message count for a user."""
        await self.queue_batch_operation(
            """INSERT OR REPLACE INTO messages (user_id, guild_id, channel_id, count, last_updated)
               VALUES (?, ?, ?, COALESCE((SELECT count FROM messages WHERE user_id = ? AND guild_id = ?), 0) + 1, ?)""",
            [(user_id, guild_id, channel_id, user_id, guild_id, int(time.time()))],
            "update"
        )
    
    async def get_message_leaderboard(self, guild_id: int = None, limit: int = 10) -> List[Tuple[int, int]]:
        """Get message leaderboard with optional guild filtering."""
        if guild_id:
            query = "SELECT user_id, count FROM messages WHERE guild_id = ? ORDER BY count DESC LIMIT ?"
            params = (guild_id, limit)
        else:
            query = "SELECT user_id, SUM(count) as total_count FROM messages GROUP BY user_id ORDER BY total_count DESC LIMIT ?"
            params = (limit,)
        
        return await self.execute_query(query, params, fetch_all=True) or []
    
    # Voice tracking methods
    async def update_voice_join(self, user_id: int, guild_id: int):
        """Record user joining voice channel."""
        await self.queue_batch_operation(
            """INSERT OR REPLACE INTO voice (user_id, guild_id, total_time, join_time, last_updated)
               VALUES (?, ?, COALESCE((SELECT total_time FROM voice WHERE user_id = ? AND guild_id = ?), 0), ?, ?)""",
            [(user_id, guild_id, user_id, guild_id, int(time.time()), int(time.time()))],
            "update"
        )
    
    async def update_voice_leave(self, user_id: int, guild_id: int):
        """Record user leaving voice channel and calculate time spent."""
        current_time = int(time.time())
        
        # Get join time
        result = await self.execute_query(
            "SELECT join_time, total_time FROM voice WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
            fetch_one=True
        )
        
        if result and result[0]:
            join_time, total_time = result
            session_time = current_time - join_time
            new_total_time = total_time + session_time
            
            await self.queue_batch_operation(
                "UPDATE voice SET total_time = ?, join_time = NULL, last_updated = ? WHERE user_id = ? AND guild_id = ?",
                [(new_total_time, current_time, user_id, guild_id)],
                "update"
            )
    
    async def get_voice_leaderboard(self, guild_id: int = None, limit: int = 10) -> List[Tuple[int, int]]:
        """Get voice leaderboard with real-time calculations."""
        current_time = int(time.time())
        
        if guild_id:
            query = """SELECT user_id, 
                             CASE 
                                WHEN join_time IS NOT NULL 
                                THEN total_time + (? - join_time)
                                ELSE total_time
                             END as current_total
                      FROM voice 
                      WHERE guild_id = ?
                      ORDER BY current_total DESC 
                      LIMIT ?"""
            params = (current_time, guild_id, limit)
        else:
            query = """SELECT user_id, 
                             SUM(CASE 
                                WHEN join_time IS NOT NULL 
                                THEN total_time + (? - join_time)
                                ELSE total_time
                             END) as current_total
                      FROM voice 
                      GROUP BY user_id
                      ORDER BY current_total DESC 
                      LIMIT ?"""
            params = (current_time, limit)
        
        return await self.execute_query(query, params, fetch_all=True) or []
    
    # Settings methods
    async def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value."""
        result = await self.execute_query(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
            fetch_one=True
        )
        return result[0] if result else None
    
    async def set_setting(self, key: str, value: str):
        """Set a setting value."""
        await self.queue_batch_operation(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, int(time.time()))],
            "update"
        )
    
    # User cache methods
    async def cache_user(self, user_id: int, username: str, discriminator: str):
        """Cache user information."""
        await self.queue_batch_operation(
            "INSERT OR REPLACE INTO user_cache (user_id, username, discriminator, cached_at) VALUES (?, ?, ?, ?)",
            [(user_id, username, discriminator, int(time.time()))],
            "insert"
        )
    
    async def get_cached_user(self, user_id: int) -> Optional[Tuple[str, str]]:
        """Get cached user information."""
        result = await self.execute_query(
            "SELECT username, discriminator FROM user_cache WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        return result if result else None
    
    # Maintenance methods
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data to maintain performance."""
        cutoff_time = int(time.time()) - (days * 24 * 60 * 60)
        
        cleanup_queries = [
            ("DELETE FROM user_cache WHERE cached_at < ?", (cutoff_time,)),
            ("DELETE FROM settings WHERE updated_at < ? AND key LIKE 'temp_%'", (cutoff_time,)),
        ]
        
        for query, params in cleanup_queries:
            try:
                await self.execute_query(query, params)
                self.logger.info(f"Cleaned up old data: {query}")
            except Exception as e:
                self.logger.error(f"Cleanup failed for {query}: {e}")
    
    async def reset_leaderboard_data(self):
        """Reset all leaderboard data for 30-day refresh cycle."""
        try:
            # Reset message counts
            await self.execute_query("DELETE FROM messages")
            
            # Reset voice times
            await self.execute_query("DELETE FROM voice")
            
            # Keep user cache for username resolution but clean old entries
            current_time = int(time.time())
            old_cache_cutoff = current_time - (7 * 24 * 3600)  # Keep cache for 7 days
            await self.execute_query(
                "DELETE FROM user_cache WHERE cached_at < ?",
                (old_cache_cutoff,)
            )
            
            # Update the last reset timestamp
            await self.execute_query(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                ("last_leaderboard_reset", str(current_time), current_time)
            )
            
            self.logger.info("Reset all leaderboard data for 30-day refresh cycle")
            
        except Exception as e:
            self.logger.error(f"Error resetting leaderboard data: {e}")
            raise
    
    async def should_reset_leaderboard(self, refresh_days: int = 30) -> bool:
        """Check if leaderboard should be reset based on refresh interval."""
        try:
            last_reset = await self.get_setting("last_leaderboard_reset")
            if not last_reset:
                return True  # Never reset before
            
            current_time = int(time.time())
            last_reset_time = int(last_reset)
            days_since_reset = (current_time - last_reset_time) / (24 * 3600)
            
            return days_since_reset >= refresh_days
            
        except Exception as e:
            self.logger.error(f"Error checking reset status: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = self._operation_stats.copy()
        
        # Add table sizes
        table_stats = {}
        for table in ['messages', 'voice', 'settings', 'user_cache']:
            result = await self.execute_query(f"SELECT COUNT(*) FROM {table}", fetch_one=True)
            table_stats[f"{table}_count"] = result[0] if result else 0
        
        stats.update(table_stats)
        return stats

    # User cache methods
    async def get_cached_user(self, user_id: int) -> Optional[Tuple[str, str]]:
        """Get cached user information."""
        result = await self.execute_query(
            "SELECT username, discriminator FROM user_cache WHERE user_id = ?",
            (user_id,),
            fetch_one=True
        )
        return result if result else None
    
    async def cache_user(self, user_id: int, username: str, discriminator: str):
        """Cache user information."""
        await self.execute_query(
            "INSERT OR REPLACE INTO user_cache (user_id, username, discriminator, cached_at) VALUES (?, ?, ?, ?)",
            (user_id, username, discriminator, int(time.time()))
        )
    
    # Cleanup methods
    async def cleanup_old_data(self):
        """Clean up old data."""
        try:
            cutoff_time = int(time.time()) - (30 * 24 * 3600)
            await self.execute_query(
                "DELETE FROM user_cache WHERE cached_at < ?",
                (cutoff_time,)
            )
            self.logger.info("Completed database cleanup")
        except Exception as e:
            self.logger.error(f"Error in database cleanup: {e}")
    
    async def close(self):
        """Close database connections and cleanup."""
        try:
            if self._batch_task:
                self._batch_task.cancel()
                try:
                    await self._batch_task
                except asyncio.CancelledError:
                    pass
            
            # Process remaining batch operations
            remaining_ops = []
            while not self._batch_queue.empty():
                try:
                    op = self._batch_queue.get_nowait()
                    remaining_ops.append(op)
                except asyncio.QueueEmpty:
                    break
            
            if remaining_ops:
                await self._execute_batch_operations(remaining_ops)
            
            self.pool.close_all()
            self.logger.info("Database manager closed successfully")
            
        except Exception as e:
            self.logger.error(f"Error closing database manager: {e}")
