#!/usr/bin/env python3
# Database Manager - Manages SQLite database operations

import os
import sqlite3
import threading
import time
import json
from datetime import datetime, timedelta

class DatabaseManager:
    """
    Manages SQLite database operations for event logging and configuration
    """
    
    def __init__(self, resource_provider):
        """
        Initialize the database manager
        
        Args:
            resource_provider: The resource provider for config and logging
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        
        # Get database path from config
        self.db_path = self.config.get('database', {}).get('path', 'database/zvision.db')
        
        # Ensure database directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Thread safety for database access
        self.db_lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        self.logger.info(f"DatabaseManager initialized with database at {self.db_path}")
    
    def _init_database(self):
        """
        Initialize the database tables if they don't exist
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                # Create events table (general purpose for all events)
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    type TEXT NOT NULL,
                    data TEXT
                )
                ''')
                
                # Additional tables for specific purposes
                
                # Create detection events table (specific for detection events)
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS detection_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    direction TEXT,
                    confidence REAL,
                    details TEXT
                )
                ''')
                
                # Create system logs table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                ''')
                
                # Create settings table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                ''')
                
                conn.commit()
                conn.close()
                
                self.logger.info("Database tables initialized")
                
            except Exception as e:
                self.logger.error(f"Error initializing database: {e}")
    
    def log_event(self, event_type, data=None):
        """
        Log a general event to the database
        
        Args:
            event_type: Type of event
            data: Data associated with the event (will be converted to JSON)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Convert data to JSON if it's a dict
                data_str = None
                if data is not None:
                    data_str = json.dumps(data)
                
                cursor.execute(
                    "INSERT INTO events (type, data) VALUES (?, ?)",
                    (event_type, data_str)
                )
                
                conn.commit()
                conn.close()
                
                self.logger.debug(f"Logged event: {event_type}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error logging event: {e}")
                return False
    
    def log_detection_event(self, event_type, direction=None, confidence=None, details=None):
        """
        Log a detection event to the database
        
        Args:
            event_type: Type of event (e.g., 'detection_start', 'detection_end')
            direction: Movement direction (e.g., 'left_to_right', 'right_to_left', 'unknown')
            confidence: Detection confidence (float)
            details: Additional details (JSON string or text)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute(
                    "INSERT INTO detection_events (timestamp, event_type, direction, confidence, details) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (timestamp, event_type, direction, confidence, details)
                )
                
                conn.commit()
                conn.close()
                
                self.logger.debug(f"Logged detection event: {event_type}, direction: {direction}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error logging detection event: {e}")
                return False
    
    def log_system_event(self, level, module, message):
        """
        Log a system event to the database
        
        Args:
            level: Log level (e.g., 'INFO', 'ERROR')
            module: Module name
            message: Log message
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute(
                    "INSERT INTO system_logs (timestamp, level, module, message) "
                    "VALUES (?, ?, ?, ?)",
                    (timestamp, level, module, message)
                )
                
                conn.commit()
                conn.close()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error logging system event: {e}")
                return False
    
    def get_events(self, limit=100):
        """
        Get recent general events
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            list: List of events (dicts)
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM events ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                
                rows = cursor.fetchall()
                
                # Convert rows to list of dicts
                events = []
                for row in rows:
                    event = dict(row)
                    # Parse JSON data if present
                    if event['data'] and event['data'].strip():
                        try:
                            event['data'] = json.loads(event['data'])
                        except json.JSONDecodeError:
                            # If it's not valid JSON, leave as is
                            pass
                    events.append(event)
                
                conn.close()
                
                return events
                
            except Exception as e:
                self.logger.error(f"Error getting events: {e}")
                return []
    
    def get_recent_detection_events(self, limit=100):
        """
        Get recent detection events
        
        Args:
            limit: Maximum number of events to return
            
        Returns:
            list: List of events (dicts)
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM detection_events ORDER BY timestamp DESC LIMIT ?",
                    (limit,)
                )
                
                results = [dict(row) for row in cursor.fetchall()]
                
                conn.close()
                
                return results
                
            except Exception as e:
                self.logger.error(f"Error getting recent detection events: {e}")
                return []
    
    def get_setting(self, key, default=None):
        """
        Get a setting from the database
        
        Args:
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            str: Setting value or default
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                result = cursor.fetchone()
                
                conn.close()
                
                if result:
                    return result[0]
                else:
                    return default
                
            except Exception as e:
                self.logger.error(f"Error getting setting {key}: {e}")
                return default
    
    def set_setting(self, key, value):
        """
        Set a setting in the database
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, str(value), timestamp)
                )
                
                conn.commit()
                conn.close()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error setting {key}: {e}")
                return False
    
    def get_detection_count_by_direction(self, days=7):
        """
        Get detection counts by direction for the specified number of days
        
        Args:
            days: Number of days to include
            
        Returns:
            dict: Counts by direction
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Calculate date threshold
                date_threshold = (datetime.now() - 
                                 timedelta(days=days)).strftime("%Y-%m-%d")
                
                cursor.execute(
                    "SELECT direction, COUNT(*) as count FROM detection_events "
                    "WHERE timestamp >= ? AND event_type = 'detection_end' "
                    "GROUP BY direction",
                    (date_threshold,)
                )
                
                results = {row[0]: row[1] for row in cursor.fetchall()}
                
                conn.close()
                
                # Ensure all directions have a value
                for direction in ['left_to_right', 'right_to_left', 'unknown']:
                    if direction not in results:
                        results[direction] = 0
                
                return results
                
            except Exception as e:
                self.logger.error(f"Error getting detection counts: {e}")
                return {'left_to_right': 0, 'right_to_left': 0, 'unknown': 0}
    
    def close(self):
        """
        Close database connection (if using a persistent connection)
        """
        # Since we're using connection per operation, this is just a placeholder
        # If we switch to a persistent connection, we would close it here
        self.logger.info("Database manager closed") 