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
        
        # Load YOLOv8 model
        self._load_model()
        
        # Tracking history for determining direction
        self.position_history = deque(maxlen=20)  # Track recent positions for direction determination
        
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
            
            self.logger.info("Detection thread stopped and state reset")
    
    def _detection_loop(self):
        """
        Main loop for person detection and tracking
        """
        frame_interval_idle = 1.0 / self.idle_fps if self.idle_fps > 0 else 1.0
        frame_interval_active = 1.0 / self.active_fps if self.active_fps > 0 else 0.2
        
        last_frame_time = 0
        no_person_counter = 0  # Count consecutive frames with no person
        
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
                self._detect_and_track(frame, no_person_counter)
                
            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}")
                time.sleep(0.1)
    
    def _detect_and_track(self, frame, no_person_counter):
        """
        Detect persons in the frame and track their movement
        
        Args:
            frame: The frame to process
            no_person_counter: Counter for consecutive frames with no person
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
                    person_detected = True
                    # Get bounding box: x1, y1, x2, y2
                    xyxy = box.xyxy[0].cpu().numpy()
                    person_bbox = xyxy
                    break
        
        # Update detection state
        with self.state_lock:
            # Handle person appearance
            if person_detected:
                now = time.time()
                no_person_counter = 0
                
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
                    no_person_counter += 1
                    # If person was present but now missing for a few frames, consider they disappeared
                    if no_person_counter >= 5:  # 5 consecutive frames
                        self.person_detected = False
                        direction_str = self._direction_to_string(self.current_direction)
                        self.current_direction = self.DIRECTION_UNKNOWN
                        self.position_history.clear()
                        self.logger.info(f"Person lost - switching to idle mode, last direction: {direction_str}")
                        
                        # Log to database if available
                        if self.db_manager:
                            self.db_manager.log_detection_event("detection_end", direction=direction_str)
                        
                        # Emit socket event if API manager is available
                        if self.api_manager:
                            self.api_manager.emit_event("detection_end", {
                                "message": "Person lost",
                                "last_direction": direction_str,
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                # else, if already in no-person state, just remain idle
    
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