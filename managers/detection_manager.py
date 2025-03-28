#!/usr/bin/env python3
# Detection Manager - Handles person detection and tracking

import cv2
import time
import threading
import numpy as np
from ultralytics import YOLO
from collections import deque
import logging

class DetectionManager:
    """
    Manages person detection and tracking using YOLOv8
    """
    
    # Direction constants
    DIRECTION_UNKNOWN = 0
    DIRECTION_LEFT_TO_RIGHT = 1
    DIRECTION_RIGHT_TO_LEFT = 2
    
    # Entry/Exit direction mapping constants
    ENTRY_DIRECTION_LTR = "LTR"  # Left-to-right is entry
    ENTRY_DIRECTION_RTL = "RTL"  # Right-to-left is entry
    
    def __init__(self, resource_provider, camera_manager, dashboard_manager=None, db_manager=None):
        """
        Initialize the detection manager
        
        Args:
            resource_provider: The resource provider for config and logging
            camera_manager: The camera manager for getting frames
            dashboard_manager: Optional dashboard manager for metrics tracking
            db_manager: Optional database manager for event logging
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.camera_manager = camera_manager
        self.dashboard_manager = dashboard_manager
        self.db_manager = db_manager
        self.api_manager = None  # Will be set by APIManager
        
        # Extract detection settings from config
        detection_config = self.config.get('detection', {})
        self.model_path = detection_config.get('model_path', 'yolov8n.pt')
        self.confidence_threshold = detection_config.get('confidence_threshold', 0.25)
        self.idle_fps = detection_config.get('idle_fps', 1)
        self.active_fps = detection_config.get('active_fps', 5)
        self.person_class_id = detection_config.get('person_class_id', 0)
        self.direction_threshold = detection_config.get('direction_threshold', 20)
        
        # Thread control
        self.is_running = False
        self.thread = None
        
        # Detection state with thread safety
        self.state_lock = threading.RLock()
        self.person_detected = False
        self.last_detection_time = None
        self.current_direction = self.DIRECTION_UNKNOWN
        self.no_person_counter = 0  # Count consecutive frames with no person
        
        # ROI and entry/exit direction configuration
        self.roi_coords = None  # Format: (x1, y1, x2, y2)
        self.entry_direction = None  # ENTRY_DIRECTION_LTR or ENTRY_DIRECTION_RTL
        
        # Load YOLOv8 model
        self._load_model()
        
        # Tracking history for determining direction
        self.position_history = deque(maxlen=20)  # Track recent positions for direction determination
        
        # Load ROI and entry direction settings from database if available
        self._load_roi_settings()
        
        self.logger.info("DetectionManager initialized")
    
    def _load_model(self):
        """
        Load the YOLOv8 model
        """
        try:
            self.logger.info(f"Loading YOLOv8 model from {self.model_path}...")
            self.model = YOLO(self.model_path)
            self.logger.info(f"YOLOv8 model loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading YOLOv8 model: {e}")
            self.model = None
    
    def start(self):
        """
        Start the detection thread
        """
        if self.is_running:
            self.logger.warning("Detection thread already running")
            return
        
        if self.model is None:
            self.logger.error("Cannot start detection thread: YOLOv8 model not loaded")
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._detection_loop)
        self.thread.daemon = True
        self.thread.start()
        self.logger.info("Detection thread started")
    
    def stop(self):
        """
        Stop the detection thread
        """
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=1.0)
            
            # Reset detection state when stopped
            with self.state_lock:
                self.person_detected = False
                self.current_direction = self.DIRECTION_UNKNOWN
                self.position_history.clear()
                self.no_person_counter = 0
            
            self.logger.info("Detection thread stopped and state reset")
    
    def _detection_loop(self):
        """
        Main loop for person detection and tracking
        """
        frame_interval_idle = 1.0 / self.idle_fps if self.idle_fps > 0 else 1.0
        frame_interval_active = 1.0 / self.active_fps if self.active_fps > 0 else 0.2
        
        last_frame_time = 0
        
        while self.is_running:
            try:
                # Determine current processing rate based on whether a person is detected
                with self.state_lock:
                    is_person_detected = self.person_detected
                
                current_interval = frame_interval_active if is_person_detected else frame_interval_idle
                
                # Check if it's time to process the next frame
                current_time = time.time()
                if current_time - last_frame_time < current_interval:
                    time.sleep(0.01)  # Small sleep to avoid busy waiting
                    continue
                
                last_frame_time = current_time
                
                # Get the latest frame
                frame = self.camera_manager.get_latest_frame()
                if frame is None:
                    # No frame available, sleep and try again
                    time.sleep(0.1)
                    continue
                
                # Run person detection
                self._process_frame(frame)
                
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)
    
    def _process_frame(self, frame):
        """
        Process a single frame: detect person and update state
        
        Args:
            frame: The frame to process
        """
        if self.model is None:
            return
        
        # Run YOLOv8 inference
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        
        # Check if any person is detected
        person_detected = False
        person_bbox = None
        
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # Check if detection is a person
                cls = int(box.cls[0])
                if cls == self.person_class_id:
                    # Get bounding box: x1, y1, x2, y2
                    xyxy = box.xyxy[0].cpu().numpy()
                    
                    # Check if person is within ROI if ROI is set
                    if self.roi_coords:
                        center_x = (xyxy[0] + xyxy[2]) / 2
                        center_y = (xyxy[1] + xyxy[3]) / 2
                        rx1, ry1, rx2, ry2 = self.roi_coords
                        
                        # Skip if person is outside ROI
                        if not (rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2):
                            continue
                    
                    person_detected = True
                    person_bbox = xyxy
                    break
        
        # Update detection state
        with self.state_lock:
            # Handle person appearance
            if person_detected:
                now = time.time()
                self.no_person_counter = 0
                
                # Handle transition from no person to person detected
                if not self.person_detected:
                    self.person_detected = True
                    self.last_detection_time = now
                    self.position_history.clear()
                    self.current_direction = self.DIRECTION_UNKNOWN
                    self.logger.info("Person detected - switching to active mode")
                    
                    # Log to dashboard and database if available
                    if self.dashboard_manager:
                        self.dashboard_manager.record_detection()
                    if self.db_manager:
                        self.db_manager.log_detection_event("detection_start", direction=None)
                    
                    # Emit socket event if API manager is available
                    if self.api_manager:
                        self.api_manager.emit_event("detection_start", {
                            "message": "Person detected",
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        })
                
                # Track person movement to determine direction
                if person_bbox is not None:
                    self._update_direction(person_bbox)
            else:
                # No person detected in this frame
                if self.person_detected:
                    self.no_person_counter += 1
                    # If person was present but now missing for a few frames, consider they disappeared
                    if self.no_person_counter >= 5:  # 5 consecutive frames
                        self.person_detected = False
                        direction_str = self._direction_to_string(self.current_direction)
                        
                        # Map direction to entry/exit if entry_direction is set
                        event_type = "detection_end"
                        if self.entry_direction and direction_str != "unknown":
                            if direction_str == "left_to_right":
                                event_type = "entry" if self.entry_direction == self.ENTRY_DIRECTION_LTR else "exit"
                            elif direction_str == "right_to_left":
                                event_type = "entry" if self.entry_direction == self.ENTRY_DIRECTION_RTL else "exit"
                        
                        self.current_direction = self.DIRECTION_UNKNOWN
                        self.position_history.clear()
                        self.logger.info(f"Person lost - switching to idle mode, last direction: {direction_str}, event type: {event_type}")
                        
                        # Log to database if available
                        if self.db_manager:
                            self.db_manager.log_detection_event(event_type, direction=direction_str)
                        
                        # Update dashboard with entry/exit if available
                        if self.dashboard_manager and hasattr(self.dashboard_manager, 'record_footfall'):
                            self.dashboard_manager.record_footfall(event_type)
                        
                        # Emit socket event if API manager is available
                        if self.api_manager:
                            self.api_manager.emit_event(event_type, {
                                "message": "Person lost",
                                "last_direction": direction_str,
                                "event_type": event_type,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
    
    def _update_direction(self, bbox):
        """
        Update the movement direction based on bounding box positions
        
        Args:
            bbox: Bounding box coordinates (x1, y1, x2, y2)
        """
        # Calculate center point of bounding box
        center_x = (bbox[0] + bbox[2]) / 2
        
        # Add to position history
        self.position_history.append(center_x)
        
        # Need at least a few points to determine direction
        if len(self.position_history) < 5:
            return
        
        # Calculate movement by comparing oldest and newest positions
        oldest_x = self.position_history[0]
        newest_x = self.position_history[-1]
        
        x_movement = newest_x - oldest_x
        
        # Only update direction if movement exceeds threshold
        if abs(x_movement) > self.direction_threshold:
            old_direction = self.current_direction
            
            if x_movement > 0:
                self.current_direction = self.DIRECTION_LEFT_TO_RIGHT
                direction_str = "left_to_right"
                self.logger.debug("Person moving LEFT to RIGHT")
            else:
                self.current_direction = self.DIRECTION_RIGHT_TO_LEFT
                direction_str = "right_to_left"
                self.logger.debug("Person moving RIGHT to LEFT")
            
            # If direction has changed, log it
            if old_direction != self.current_direction:
                self.logger.info(f"Direction determined: {direction_str}")
                
                # Log to dashboard and database if available
                if self.dashboard_manager:
                    self.dashboard_manager.record_direction(direction_str)
                if self.db_manager:
                    self.db_manager.log_detection_event("direction", direction=direction_str)
                
                # Emit socket event if API manager is available
                if self.api_manager:
                    self.api_manager.emit_event("direction", {
                        "direction": direction_str,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
    
    def _direction_to_string(self, direction):
        """
        Convert direction constant to string
        
        Args:
            direction: Direction constant
            
        Returns:
            str: Direction as string
        """
        if direction == self.DIRECTION_LEFT_TO_RIGHT:
            return "left_to_right"
        elif direction == self.DIRECTION_RIGHT_TO_LEFT:
            return "right_to_left"
        else:
            return "unknown"
    
    def is_person_detected(self):
        """
        Check if a person is currently detected
        
        Returns:
            bool: True if a person is detected, False otherwise
        """
        with self.state_lock:
            return self.person_detected
    
    def get_direction(self):
        """
        Get the current movement direction
        
        Returns:
            int: Direction constant (UNKNOWN, LEFT_TO_RIGHT, RIGHT_TO_LEFT)
        """
        with self.state_lock:
            return self.current_direction
    
    def get_detection_status(self):
        """
        Get the current detection status
        
        Returns:
            dict: Status information including detection state and direction
        """
        with self.state_lock:
            direction_str = self._direction_to_string(self.current_direction)
            
            return {
                "person_detected": self.person_detected,
                "last_detection_time": self.last_detection_time,
                "direction": direction_str,
            }
    
    def _load_roi_settings(self):
        """
        Load ROI and entry direction settings from database
        """
        if self.db_manager:
            try:
                # Try loading from the new camera_config table first
                roi_config = self.db_manager.get_camera_roi(0)  # Default camera ID
                if roi_config:
                    coords = roi_config["coords"]
                    self.roi_coords = (coords["x1"], coords["y1"], coords["x2"], coords["y2"])
                    self.entry_direction = roi_config["entry_direction"]
                    self.logger.info(f"Loaded ROI coordinates: {self.roi_coords} and entry direction: {self.entry_direction}")
                    return
                
                # Backward compatibility: Try loading from the old settings table
                roi_str = self.db_manager.get_setting('roi_coords')
                if roi_str and roi_str.strip():  # Check if string is not empty
                    try:
                        import json
                        coords = json.loads(roi_str)
                        if coords and len(coords) == 4:  # Validate tuple has 4 elements
                            self.roi_coords = tuple(coords)
                            self.logger.info(f"Loaded ROI coordinates from legacy settings: {self.roi_coords}")
                            
                            # Load entry direction from old settings
                            self.entry_direction = self.db_manager.get_setting('entry_direction')
                            if self.entry_direction:
                                self.logger.info(f"Loaded entry direction from legacy settings: {self.entry_direction}")
                            
                            # Migrate to the new table
                            self.db_manager.save_camera_roi(0, self.roi_coords, self.entry_direction)
                            self.logger.info("Migrated ROI settings to new camera_config table")
                        else:
                            self.logger.warning(f"Invalid ROI coordinates format, expected 4 values: {coords}")
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"Could not parse ROI coordinates as JSON: {e}")
            except Exception as e:
                self.logger.error(f"Error loading ROI settings: {e}")
                # Don't re-raise the exception - just log it
    
    def set_roi(self, roi_coords):
        """
        Set the Region of Interest coordinates
        
        Args:
            roi_coords: Tuple of (x1, y1, x2, y2) defining the ROI rectangle
        """
        with self.state_lock:
            self.roi_coords = roi_coords
            
            # Save to database if available
            if self.db_manager:
                # Save to the new camera_config table
                self.db_manager.save_camera_roi(0, roi_coords, self.entry_direction or self.ENTRY_DIRECTION_LTR)
                
            self.logger.info(f"ROI set to {roi_coords}")
    
    def set_entry_direction(self, entry_direction):
        """
        Set which direction is considered as an entry
        
        Args:
            entry_direction: Either ENTRY_DIRECTION_LTR or ENTRY_DIRECTION_RTL
        """
        if entry_direction not in [self.ENTRY_DIRECTION_LTR, self.ENTRY_DIRECTION_RTL]:
            self.logger.error(f"Invalid entry direction: {entry_direction}")
            return
            
        with self.state_lock:
            self.entry_direction = entry_direction
            
            # Save to database if available
            if self.db_manager and self.roi_coords:
                # Update the entry direction in the camera_config table
                self.db_manager.save_camera_roi(0, self.roi_coords, entry_direction)
                
            self.logger.info(f"Entry direction set to {entry_direction}")
    
    def get_roi(self):
        """
        Get the current ROI coordinates
        
        Returns:
            tuple: The current ROI coordinates (x1, y1, x2, y2) or None if not set
        """
        with self.state_lock:
            return self.roi_coords
    
    def get_entry_direction(self):
        """
        Get the current entry direction setting
        
        Returns:
            str: The current entry direction setting or None if not set
        """
        with self.state_lock:
            return self.entry_direction
    
    def clear_roi(self):
        """
        Clear the ROI setting
        """
        with self.state_lock:
            self.roi_coords = None
            self.entry_direction = None
            
            # Remove from database if available
            if self.db_manager:
                # Delete from the camera_config table
                self.db_manager.delete_camera_roi(0)
                
            self.logger.info("ROI and entry direction cleared") 