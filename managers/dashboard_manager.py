#!/usr/bin/env python3
# Dashboard Manager - Collects analytics and metrics

import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque

class DashboardManager:
    """
    Manages analytics and metrics collection
    """
    
    def __init__(self, resource_provider, detection_manager=None):
        """
        Initialize the dashboard manager
        
        Args:
            resource_provider: The resource provider for config and logging
            detection_manager: The detection manager for monitoring detection events
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.detection_manager = detection_manager
        
        # Thread safety
        self.metrics_lock = threading.Lock()
        
        # Metrics storage
        self.detection_count = 0
        self.direction_counts = {
            "left_to_right": 0,
            "right_to_left": 0,
            "unknown": 0
        }
        
        # For hourly metrics
        self.hourly_stats = defaultdict(lambda: {
            "detection_count": 0,
            "left_to_right": 0,
            "right_to_left": 0,
            "unknown": 0
        })
        
        # Detection history (for recent events)
        self.detection_history = deque(maxlen=100)  # Store last 100 detection events
        
        # Last detection time and direction
        self.last_detection_time = None
        self.last_direction = None
        
        self.logger.info("DashboardManager initialized")
        
        # Start background monitoring thread if detection manager is provided
        if detection_manager:
            self.is_running = True
            self.monitor_thread = threading.Thread(target=self._monitor_detections)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def record_detection(self):
        """
        Record a new person detection
        """
        with self.metrics_lock:
            self.detection_count += 1
            self.last_detection_time = time.time()
            
            # Add to hourly stats
            hour_key = datetime.now().strftime("%Y-%m-%d %H:00")
            self.hourly_stats[hour_key]["detection_count"] += 1
            
            self.logger.info(f"Total detections incremented: {self.detection_count}")
    
    def record_direction(self, direction):
        """
        Record a direction of movement
        
        Args:
            direction (str): Direction of movement ('left_to_right', 'right_to_left', 'unknown')
        """
        with self.metrics_lock:
            if direction in self.direction_counts:
                self.direction_counts[direction] += 1
            else:
                self.direction_counts[direction] = 0
                
            self.last_direction = direction
            
            # Add to hourly stats
            hour_key = datetime.now().strftime("%Y-%m-%d %H:00")
            self.hourly_stats[hour_key][direction] += 1
            
            # Add to history
            self.detection_history.append({
                "timestamp": time.time(),
                "direction": direction,
                "duration": 0  # Placeholder, would be updated when person leaves
            })
            
            self.logger.info(f"Recorded direction: {direction}")
    
    def _monitor_detections(self):
        """
        Background thread to monitor detection events and update metrics
        """
        last_status = {"person_detected": False, "direction": "unknown"}
        
        while self.is_running:
            try:
                # Get current detection status
                status = self.detection_manager.get_detection_status()
                
                # Check for detection start/end events
                self._process_detection_events(last_status, status)
                
                # Update last status
                last_status = status.copy()
                
                # Sleep to avoid busy waiting
                time.sleep(0.2)
                
            except Exception as e:
                self.logger.error(f"Error in dashboard monitoring: {e}")
                time.sleep(1.0)
    
    def _process_detection_events(self, last_status, current_status):
        """
        Process detection events and update metrics
        
        Args:
            last_status: Previous detection status
            current_status: Current detection status
        """
        try:
            # Person appearance/disappearance transitions
            was_detected = last_status.get("person_detected", False)
            is_detected = current_status.get("person_detected", False)
            
            # Check for person leaving the frame (was detected, now not detected)
            if was_detected and not is_detected:
                with self.metrics_lock:
                    # Update duration of the last detection event if it exists
                    if self.detection_history:
                        last_event = self.detection_history[-1]
                        if last_event.get("duration", 0) == 0:  # Still open/active
                            now = time.time()
                            event_start = last_event.get("timestamp", now)
                            duration = now - event_start
                            last_event["duration"] = duration
                            self.logger.info(f"Person left frame - detection duration: {duration:.2f} seconds")
                
                # Log the event to the database if available
                if hasattr(self.detection_manager, 'db_manager') and self.detection_manager.db_manager:
                    direction = last_status.get("direction", "unknown")
                    self.detection_manager.db_manager.log_detection_event(
                        "detection_end", 
                        direction=direction
                    )
            
            # Check for person appearance (wasn't detected, now detected)
            # This is handled primarily by DetectionManager calling record_detection,
            # but this is a backup in case that didn't happen
            elif not was_detected and is_detected:
                # Only record if the last_detection_time doesn't match the event
                # This prevents duplicate recording if DetectionManager already called record_detection
                current_detection_time = current_status.get("last_detection_time")
                if current_detection_time and current_detection_time != self.last_detection_time:
                    self.logger.info("Detected person appearance via monitoring")
                    self.record_detection()
            
            # Check for direction changes
            last_direction = last_status.get("direction", "unknown")
            current_direction = current_status.get("direction", "unknown")
            
            if current_direction != "unknown" and current_direction != last_direction:
                self.logger.info(f"Direction change detected: {current_direction}")
                # Record the new direction
                self.record_direction(current_direction)
                
        except Exception as e:
            self.logger.error(f"Error processing detection events: {e}")
    
    def get_total_metrics(self):
        """
        Get total detection metrics
        
        Returns:
            dict: Detection counts and direction statistics
        """
        with self.metrics_lock:
            return {
                "detection_count": self.detection_count,
                "direction_counts": self.direction_counts.copy()
            }
    
    def get_hourly_metrics(self, hours=24):
        """
        Get hourly detection metrics for the specified number of hours
        
        Args:
            hours: Number of hours to include (default: 24)
            
        Returns:
            dict: Hourly detection statistics
        """
        now = datetime.now()
        start_time = now - timedelta(hours=hours)
        
        # Format for comparison
        start_hour = start_time.strftime("%Y-%m-%d %H:00")
        
        with self.metrics_lock:
            # Filter hourly stats to include only the specified hours
            filtered_stats = {
                hour: stats.copy() 
                for hour, stats in self.hourly_stats.items() 
                if hour >= start_hour
            }
            
            return filtered_stats
    
    def get_recent_detections(self, count=10):
        """
        Get recent detection events
        
        Args:
            count: Number of recent events to include (default: 10)
            
        Returns:
            list: Recent detection events
        """
        with self.metrics_lock:
            # Get only the specified number of most recent events
            recent = list(self.detection_history)[-count:]
            
            # Format timestamps as strings
            for event in recent:
                event["timestamp"] = datetime.fromtimestamp(
                    event["timestamp"]
                ).strftime("%Y-%m-%d %H:%M:%S")
            
            return recent
    
    def get_summary(self):
        """
        Get a summary of current stats for dashboard display
        
        Returns:
            dict: Summary of all current statistics
        """
        with self.metrics_lock:
            # Format timestamp for display if it exists
            last_detection_time_str = None
            if self.last_detection_time:
                last_detection_time_str = datetime.fromtimestamp(
                    self.last_detection_time
                ).strftime("%Y-%m-%d %H:%M:%S")
            
            return {
                "total_detections": self.detection_count,
                "direction_counts": self.direction_counts.copy(),
                "last_detection_time": last_detection_time_str,
                "last_direction": self.last_direction
            }
    
    def get_current_status(self):
        """
        Get current detection status
        
        Returns:
            dict: Current system status including detection state
        """
        status = self.detection_manager.get_detection_status() if self.detection_manager else {}
        
        # Format timestamp if it exists
        if status.get("last_detection_time"):
            status["last_detection_time"] = datetime.fromtimestamp(
                status["last_detection_time"]
            ).strftime("%Y-%m-%d %H:%M:%S")
        
        return status
    
    def get_footfall_count(self):
        """
        Get the total footfall count (total number of detections)
        
        Returns:
            int: Footfall count
        """
        with self.metrics_lock:
            return self.detection_count
            
    def get_detection_metrics_by_day(self, days=7):
        """
        Get detection metrics grouped by day for the specified period
        
        Args:
            days: Number of days to include (default: 7)
            
        Returns:
            dict: Daily detection metrics
        """
        daily_metrics = {}
        now = datetime.now()
        
        with self.metrics_lock:
            # Process hourly stats to create daily aggregates
            for hour_key, stats in self.hourly_stats.items():
                try:
                    # Parse hour_key (format: "YYYY-MM-DD HH:00")
                    hour_date = datetime.strptime(hour_key, "%Y-%m-%d %H:00")
                    
                    # Check if within the specified days
                    if (now - hour_date).days <= days:
                        # Extract just the date part
                        date_key = hour_date.strftime("%Y-%m-%d")
                        
                        # Initialize date entry if not exists
                        if date_key not in daily_metrics:
                            daily_metrics[date_key] = {
                                "detection_count": 0,
                                "left_to_right": 0,
                                "right_to_left": 0,
                                "unknown": 0
                            }
                        
                        # Add hourly stats to daily totals
                        daily_metrics[date_key]["detection_count"] += stats["detection_count"]
                        daily_metrics[date_key]["left_to_right"] += stats["left_to_right"]
                        daily_metrics[date_key]["right_to_left"] += stats["right_to_left"]
                        daily_metrics[date_key]["unknown"] += stats["unknown"]
                except Exception as e:
                    self.logger.error(f"Error processing hourly stats for {hour_key}: {e}")
                    continue
        
        return daily_metrics 