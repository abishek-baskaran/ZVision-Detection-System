#!/usr/bin/env python3
# Database Manager - Manages SQLite database operations

import os
import sqlite3
import threading
import time
import json
from datetime import datetime, timedelta
import pytz

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
                
                # Ensure the detection_events table has a camera_id column
                try:
                    cursor.execute("SELECT camera_id FROM detection_events LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    cursor.execute("ALTER TABLE detection_events ADD COLUMN camera_id TEXT")
                
                # Ensure the detection_events table has a snapshot_path column
                try:
                    cursor.execute("SELECT snapshot_path FROM detection_events LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    self.logger.info("Adding snapshot_path column to detection_events table")
                    cursor.execute("ALTER TABLE detection_events ADD COLUMN snapshot_path TEXT")
                
                # Create index on camera_id and timestamp for faster analytics queries
                cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_camera_ts ON detection_events(camera_id, timestamp)
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
                
                # Create camera_config table for ROI and direction settings
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS camera_config (
                    camera_id TEXT PRIMARY KEY,
                    roi_x1 INTEGER,
                    roi_y1 INTEGER,
                    roi_x2 INTEGER,
                    roi_y2 INTEGER,
                    entry_direction TEXT
                )
                ''')
                
                # Create cameras table if it doesn't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS cameras (
                    camera_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    name TEXT,
                    width INTEGER,
                    height INTEGER,
                    fps INTEGER,
                    enabled INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    
    def log_detection_event(self, event_type, direction=None, confidence=None, details=None, camera_id=None, snapshot_path=None):
        """
        Log a detection event to the database
        
        Args:
            event_type: Type of event (e.g., 'detection_start', 'detection_end')
            direction: Movement direction (e.g., 'left_to_right', 'right_to_left', 'unknown')
            confidence: Detection confidence (float)
            details: Additional details (JSON string or text)
            camera_id: ID of the camera that generated the event
            snapshot_path: Path to saved snapshot image (if any)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Ensure the detection_events table has a camera_id column
                try:
                    cursor.execute("SELECT camera_id FROM detection_events LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    self.logger.info("Adding camera_id column to detection_events table")
                    cursor.execute("ALTER TABLE detection_events ADD COLUMN camera_id TEXT")
                    conn.commit()
                
                # Ensure the detection_events table has a snapshot_path column
                try:
                    cursor.execute("SELECT snapshot_path FROM detection_events LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    self.logger.info("Adding snapshot_path column to detection_events table")
                    cursor.execute("ALTER TABLE detection_events ADD COLUMN snapshot_path TEXT")
                    conn.commit()
                
                # Use UTC timestamp for consistent timezone handling
                timestamp = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
                
                cursor.execute(
                    "INSERT INTO detection_events (timestamp, event_type, direction, confidence, details, camera_id, snapshot_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (timestamp, event_type, direction, confidence, details, camera_id, snapshot_path)
                )
                
                conn.commit()
                conn.close()
                
                self.logger.debug(f"Logged detection event: {event_type}, direction: {direction}, camera: {camera_id}, snapshot: {snapshot_path}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error logging detection event: {e}")
                return False
    
    def log_system_event(self, level, module, message):
        """
        Log a system event to the database
        
        Args:
            level: Log level (e.g., 'INFO', 'ERROR')
            module: Module or component generating the log
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
    
    def get_events(self, limit=100, from_date=None, to_date=None):
        """
        Get recent general events
        
        Args:
            limit: Maximum number of events to return
            from_date: Optional start date for filtering (format: YYYY-MM-DD)
            to_date: Optional end date for filtering (format: YYYY-MM-DD)
            
        Returns:
            list: List of events (dicts)
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                query = "SELECT * FROM events"
                params = []
                where_clauses = []
                
                # Add date filters if provided
                if from_date:
                    where_clauses.append("datetime(timestamp) >= datetime(?)")
                    params.append(f"{from_date} 00:00:00")
                
                if to_date:
                    where_clauses.append("datetime(timestamp) <= datetime(?)")
                    params.append(f"{to_date} 23:59:59")
                
                # Add WHERE clause if we have conditions
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                # Add order and limit
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                
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
    
    def get_recent_detection_events(self, limit=100, from_date=None, to_date=None):
        """
        Get recent detection events
        
        Args:
            limit: Maximum number of events to return
            from_date: Optional start date for filtering (format: YYYY-MM-DD)
            to_date: Optional end date for filtering (format: YYYY-MM-DD)
            
        Returns:
            list: List of events (dicts)
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                query = "SELECT * FROM detection_events"
                params = []
                where_clauses = []
                
                # Add date filters if provided
                if from_date:
                    where_clauses.append("datetime(timestamp) >= datetime(?)")
                    params.append(f"{from_date} 00:00:00")
                
                if to_date:
                    where_clauses.append("datetime(timestamp) <= datetime(?)")
                    params.append(f"{to_date} 23:59:59")
                
                # Add WHERE clause if we have conditions
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                # Add order and limit
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                
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
    
    def get_detection_count_by_direction(self, days=7, camera_id=None):
        """
        Get detection counts by direction for the specified number of days
        
        Args:
            days: Number of days to include
            camera_id: Optional camera ID to filter by
            
        Returns:
            dict: Counts by direction
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Calculate date threshold using UTC
                date_threshold = (datetime.now(pytz.UTC) - 
                                 timedelta(days=days)).strftime("%Y-%m-%d")
                
                if camera_id:
                    # Add camera_id filter if provided
                    cursor.execute(
                        "SELECT direction, COUNT(*) as count FROM detection_events "
                        "WHERE timestamp >= ? AND event_type = 'detection_end' AND camera_id = ? "
                        "GROUP BY direction",
                        (date_threshold, camera_id)
                    )
                else:
                    # Original query without camera filter
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
    
    def get_detection_count_by_direction_for_camera(self, days=7, camera_id=None):
        """
        Get detection counts by direction for a specific camera for the specified number of days
        
        Args:
            days: Number of days to include
            camera_id: ID of the camera to filter by
            
        Returns:
            dict: Counts by direction for the specified camera
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Calculate date threshold
                date_threshold = (datetime.now() - 
                                 timedelta(days=days)).strftime("%Y-%m-%d")
                
                # Add camera_id filter
                cursor.execute(
                    "SELECT direction, COUNT(*) as count FROM detection_events "
                    "WHERE timestamp >= ? AND event_type = 'detection_end' AND camera_id = ? "
                    "GROUP BY direction",
                    (date_threshold, camera_id)
                )
                
                results = {row[0]: row[1] for row in cursor.fetchall()}
                
                conn.close()
                
                # Ensure all directions have a value
                for direction in ['left_to_right', 'right_to_left', 'unknown']:
                    if direction not in results:
                        results[direction] = 0
                
                return results
                
            except Exception as e:
                self.logger.error(f"Error getting detection counts for camera {camera_id}: {e}")
                return {'left_to_right': 0, 'right_to_left': 0, 'unknown': 0}
    
    def close(self):
        """
        Close database connection (if using a persistent connection)
        """
        # Since we're using connection per operation, this is just a placeholder
        # If we switch to a persistent connection, we would close it here
        self.logger.info("Database manager closed")
    
    def save_camera_roi(self, camera_id, roi, entry_dir):
        """
        Save ROI and entry direction settings for a camera
        
        Args:
            camera_id: Camera identifier (number or string)
            roi: Tuple of (x1, y1, x2, y2) defining the ROI rectangle
            entry_dir: Direction considered as entry (LTR or RTL)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO camera_config 
                    (camera_id, roi_x1, roi_y1, roi_x2, roi_y2, entry_direction)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (str(camera_id), roi[0], roi[1], roi[2], roi[3], entry_dir))
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Saved ROI configuration for camera {camera_id}: {roi}, entry_direction: {entry_dir}")
                return True
            except Exception as e:
                self.logger.error(f"Error saving camera ROI configuration: {e}")
                return False
    
    def get_camera_roi(self, camera_id):
        """
        Get ROI and entry direction settings for a camera
        
        Args:
            camera_id: Camera identifier (number or string)
            
        Returns:
            dict: Dictionary with ROI coordinates and entry direction, or None if not found
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT roi_x1, roi_y1, roi_x2, roi_y2, entry_direction 
                    FROM camera_config 
                    WHERE camera_id = ?;
                """, (str(camera_id),))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    x1, y1, x2, y2, entry_dir = row
                    return {"coords": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}, "entry_direction": entry_dir}
                else:
                    return None
            except Exception as e:
                self.logger.error(f"Error retrieving camera ROI configuration: {e}")
                return None
    
    def delete_camera_roi(self, camera_id):
        """
        Delete ROI and entry direction settings for a camera
        
        Args:
            camera_id: Camera identifier (number or string)
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM camera_config WHERE camera_id = ?;", (str(camera_id),))
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Deleted ROI configuration for camera {camera_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error deleting camera ROI configuration: {e}")
                return False
    
    # Alias for delete_camera_roi for API compatibility
    def clear_roi(self, camera_id):
        """
        Clear ROI and entry direction settings for a camera (alias for delete_camera_roi)
        
        Args:
            camera_id: Camera identifier (number or string)
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.delete_camera_roi(camera_id)
    
    def add_camera(self, camera_id, source, name=None, width=None, height=None, fps=None):
        """
        Add a camera configuration to the database
        
        Args:
            camera_id: ID of the camera
            source: Camera source (device ID or URL)
            name: Camera name
            width: Camera width
            height: Camera height
            fps: Camera FPS
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Add to cameras table (for backward compatibility)
                cursor.execute("""
                INSERT OR REPLACE INTO cameras 
                (camera_id, source, name, width, height, fps, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
                """, (str(camera_id), source, name, width, height, fps))
                
                # Also update camera_config table to ensure both tables have the camera info
                # First check if camera exists in camera_config
                cursor.execute("SELECT camera_id FROM camera_config WHERE camera_id = ?", (str(camera_id),))
                row = cursor.fetchone()
                
                if row:
                    # Update source, name, width, height, fps without affecting ROI settings
                    cursor.execute("""
                    UPDATE camera_config 
                    SET source = ?, name = ?, width = ?, height = ?, fps = ?
                    WHERE camera_id = ?;
                    """, (source, name, width, height, fps, str(camera_id)))
                else:
                    # Insert new camera with default enabled=1
                    cursor.execute("""
                    INSERT INTO camera_config 
                    (camera_id, source, name, width, height, fps, enabled) 
                    VALUES (?, ?, ?, ?, ?, ?, 1);
                    """, (str(camera_id), source, name, width, height, fps))
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Added camera {camera_id} ({name or 'unnamed'}) with source {source} to database")
                return True
                
            except Exception as e:
                self.logger.error(f"Error adding camera to database: {e}")
                return False
    
    def remove_camera(self, camera_id):
        """
        Remove a camera configuration from the database
        
        Args:
            camera_id: ID of the camera to remove
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if the cameras table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cameras'")
                if not cursor.fetchone():
                    # Table doesn't exist, nothing to delete
                    conn.close()
                    return True
                
                # Delete camera record
                cursor.execute("DELETE FROM cameras WHERE camera_id=?", (camera_id,))
                
                # Also delete ROI settings for this camera
                self.clear_roi(camera_id)
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"Removed camera {camera_id} from database")
                return True
                
            except Exception as e:
                self.logger.error(f"Error removing camera from database: {e}")
                return False
    
    def get_cameras(self):
        """
        Get all camera configurations from the database
        
        Returns:
            list: List of camera configurations as dictionaries, or empty list if error
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                # Check if the cameras table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cameras'")
                if not cursor.fetchone():
                    # Table doesn't exist, no cameras
                    conn.close()
                    return []
                
                # Get all cameras
                cursor.execute("SELECT * FROM cameras")
                cameras = [dict(row) for row in cursor.fetchall()]
                
                # Get ROI settings for each camera
                for camera in cameras:
                    roi = self.get_camera_roi(camera['camera_id'])
                    if roi:
                        camera['roi'] = roi
                
                conn.close()
                return cameras
                
            except Exception as e:
                self.logger.error(f"Error getting cameras from database: {e}")
                return []
    
    def list_cameras(self):
        """
        List all camera configurations from the database
        
        Returns:
            list: List of camera configurations as dictionaries
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()
                
                # Get cameras with ROI settings in a single query using LEFT JOIN
                cursor.execute("""
                    SELECT c.*, 
                           r.roi_x1, r.roi_y1, r.roi_x2, r.roi_y2, r.entry_direction
                    FROM cameras c 
                    LEFT JOIN camera_config r ON c.camera_id = r.camera_id
                """)
                
                rows = cursor.fetchall()
                cameras = []
                
                for row in rows:
                    camera = dict(row)
                    cameras.append(camera)
                
                conn.close()
                return cameras
                
            except Exception as e:
                self.logger.error(f"Error listing cameras: {e}")
                return []
    
    def update_camera(self, camera_id, enabled=None, name=None, width=None, height=None, fps=None):
        """
        Update a camera configuration in the database
        
        Args:
            camera_id: ID of the camera to update
            enabled: Whether the camera is enabled (1 or 0)
            name: Camera name
            width: Camera width
            height: Camera height
            fps: Camera FPS
            
        Returns:
            bool: True if successful, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if the cameras table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cameras'")
                if not cursor.fetchone():
                    # Table doesn't exist, can't update
                    conn.close()
                    return False
                
                # Check if camera exists
                cursor.execute("SELECT camera_id FROM cameras WHERE camera_id=?", (camera_id,))
                if not cursor.fetchone():
                    # Camera doesn't exist, can't update
                    conn.close()
                    return False
                
                # Build update query with only the fields that are provided
                query = "UPDATE cameras SET updated_at=CURRENT_TIMESTAMP"
                params = []
                
                if enabled is not None:
                    query += ", enabled=?"
                    params.append(1 if enabled else 0)
                
                if name is not None:
                    query += ", name=?"
                    params.append(name)
                
                if width is not None:
                    query += ", width=?"
                    params.append(width)
                
                if height is not None:
                    query += ", height=?"
                    params.append(height)
                
                if fps is not None:
                    query += ", fps=?"
                    params.append(fps)
                
                query += " WHERE camera_id=?"
                params.append(camera_id)
                
                # Execute update if any fields to update
                if len(params) > 1:  # More than just camera_id
                    cursor.execute(query, params)
                    conn.commit()
                
                conn.close()
                
                self.logger.info(f"Updated camera {camera_id} in database")
                return True
                
            except Exception as e:
                self.logger.error(f"Error updating camera in database: {e}")
                return False
    
    def get_hourly_metrics(self, hours=24, camera_id=None):
        """
        Get hourly detection metrics for the specified number of hours
        
        Args:
            hours: Number of hours to include
            camera_id: Optional camera ID to filter by
            
        Returns:
            dict: Hourly detection statistics
        """
        with self.db_lock:
            try:
                # Log the request parameters
                self.logger.info(f"get_hourly_metrics called with hours={hours}, camera_id={camera_id}")
                
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Use Row factory for named columns
                cursor = conn.cursor()
                
                # Calculate hour threshold
                hour_threshold = (datetime.now(pytz.UTC) - 
                                timedelta(hours=hours)).strftime("%Y-%m-%d %H:00")
                self.logger.info(f"Hour threshold: {hour_threshold}")
                
                # Format the query based on whether camera_id is provided
                if camera_id is not None and camera_id != "":
                    # With camera ID filter
                    query = """
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        direction,
                        COUNT(*) as count,
                        camera_id
                    FROM detection_events 
                    WHERE strftime('%Y-%m-%d %H:00', timestamp) >= ? 
                    AND event_type = 'detection_end'
                    AND camera_id = ?
                    GROUP BY hour, direction
                    ORDER BY hour
                    """
                    # Log the query and parameters
                    self.logger.info(f"SQL query with camera_id filter: {query}")
                    self.logger.info(f"Parameters: hour_threshold={hour_threshold}, camera_id={camera_id}")
                    
                    # Check if there are any records for this camera
                    verification_query = "SELECT COUNT(*) FROM detection_events WHERE camera_id = ? AND event_type = 'detection_end'"
                    cursor.execute(verification_query, (camera_id,))
                    count = cursor.fetchone()[0]
                    self.logger.info(f"Total records for camera {camera_id} with event_type 'detection_end': {count}")
                    
                    # Execute the main query - be explicit about parameter placement
                    params = (hour_threshold, camera_id)
                    self.logger.info(f"Executing query with params: {params}")
                    cursor.execute(query, params)
                else:
                    # Without camera ID filter
                    query = """
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        direction,
                        COUNT(*) as count,
                        camera_id
                    FROM detection_events 
                    WHERE strftime('%Y-%m-%d %H:00', timestamp) >= ? 
                    AND event_type = 'detection_end'
                    GROUP BY hour, direction, camera_id
                    ORDER BY hour
                    """
                    # Log the query and parameters
                    self.logger.info(f"SQL query without camera_id filter: {query}")
                    self.logger.info(f"Parameters: hour_threshold={hour_threshold}")
                    
                    # Execute the main query
                    cursor.execute(query, (hour_threshold,))
                
                # Fetch all rows and log the raw result
                rows = cursor.fetchall()
                self.logger.info(f"Query returned {len(rows)} rows")
                if len(rows) > 0:
                    # Log the column names 
                    self.logger.info(f"Column names: {rows[0].keys()}")
                
                # Process the results - based on whether camera_id is provided
                results = {}
                for row in rows:
                    hour_key = row['hour']
                    direction = row['direction']
                    count = row['count']
                    row_camera_id = row['camera_id']
                    
                    # Skip rows that don't match our camera_id
                    if camera_id is not None and camera_id != "" and row_camera_id != camera_id:
                        self.logger.info(f"Skipping row for camera {row_camera_id} (we want {camera_id})")
                        continue
                        
                    self.logger.info(f"Processing row: hour={hour_key}, direction={direction}, count={count}, camera_id={row_camera_id}")
                    
                    # Create hour entry if not exists
                    if hour_key not in results:
                        results[hour_key] = {
                            "detection_count": 0,
                            "left_to_right": 0,
                            "right_to_left": 0,
                            "unknown": 0
                        }
                    
                    # Add to direction count - handle None direction
                    if direction is not None and direction in results[hour_key]:
                        results[hour_key][direction] += count
                    elif direction is None:
                        results[hour_key]["unknown"] += count
                    
                    # Add to total count
                    results[hour_key]["detection_count"] += count
                
                conn.close()
                
                # Log the final results
                self.logger.info(f"Final hourly metrics for camera {camera_id}: {results}")
                return results
                
            except Exception as e:
                self.logger.error(f"Error getting hourly metrics: {e}", exc_info=True)
                return {}
    
    def get_hourly_metrics_raw(self, hours=24, camera_id=None):
        """
        Get raw hourly metrics query results for debugging
        
        Args:
            hours: Number of hours to include
            camera_id: Optional camera ID to filter by
            
        Returns:
            list: Raw query results
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Calculate hour threshold
                hour_threshold = (datetime.now(pytz.UTC) - 
                                timedelta(hours=hours)).strftime("%Y-%m-%d %H:00")
                
                # Define the query based on whether camera_id is provided
                if camera_id:
                    query = """
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        direction,
                        COUNT(*) as count,
                        camera_id
                    FROM detection_events 
                    WHERE strftime('%Y-%m-%d %H:00', timestamp) >= ? 
                    AND event_type = 'detection_end'
                    AND camera_id = ?
                    GROUP BY hour, direction, camera_id
                    ORDER BY hour
                    """
                    cursor.execute(query, (hour_threshold, camera_id))
                else:
                    query = """
                    SELECT 
                        strftime('%Y-%m-%d %H:00', timestamp) as hour,
                        direction,
                        COUNT(*) as count,
                        camera_id
                    FROM detection_events 
                    WHERE strftime('%Y-%m-%d %H:00', timestamp) >= ? 
                    AND event_type = 'detection_end'
                    GROUP BY hour, direction, camera_id
                    ORDER BY hour, camera_id
                    """
                    cursor.execute(query, (hour_threshold,))
                
                # Fetch all rows
                rows = cursor.fetchall()
                
                # Convert to list of dicts for easier debugging
                result = []
                for row in rows:
                    result.append({
                        'hour': row[0],
                        'direction': row[1],
                        'count': row[2],
                        'camera_id': row[3]
                    })
                
                conn.close()
                return result
                
            except Exception as e:
                self.logger.error(f"Error getting raw hourly metrics: {e}")
                return []
    
    def is_camera_valid(self, camera_id):
        """
        Check if a camera ID exists in the database
        
        Args:
            camera_id: Camera ID to check
            
        Returns:
            bool: True if the camera exists, False otherwise
        """
        with self.db_lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check if the camera exists in the detection_events table
                query = "SELECT COUNT(*) FROM detection_events WHERE camera_id = ?"
                cursor.execute(query, (camera_id,))
                count = cursor.fetchone()[0]
                
                conn.close()
                return count > 0
                
            except Exception as e:
                self.logger.error(f"Error checking camera validity: {e}")
                return False 