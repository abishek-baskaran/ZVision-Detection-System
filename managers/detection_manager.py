#!/usr/bin/env python3
# Detection Manager - Handles person detection and tracking

import cv2
import time
import threading
import numpy as np
from ultralytics import YOLO
from collections import deque
import logging
import psutil
import os
from datetime import datetime

class DetectionManager:
    """
    Manages person detection and tracking using YOLOv8 for multiple cameras
    """
    
    # Direction constants
    DIRECTION_UNKNOWN = 0
    DIRECTION_LEFT_TO_RIGHT = 1
    DIRECTION_RIGHT_TO_LEFT = 2
    
    # Entry/Exit direction mapping constants
    ENTRY_DIRECTION_LTR = "LTR"  # Left-to-right is entry
    ENTRY_DIRECTION_RTL = "RTL"  # Right-to-left is entry
    
    def __init__(self, resource_provider, camera_registry, dashboard_manager=None, db_manager=None):
        """
        Initialize the detection manager
        
        Args:
            resource_provider: The resource provider for config and logging
            camera_registry: The camera registry for accessing cameras
            dashboard_manager: Optional dashboard manager for metrics tracking
            db_manager: Optional database manager for event logging
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.camera_registry = camera_registry
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
        
        # Dictionary to hold detection threads and states for each camera
        self.detection_threads = {}
        self.states = {}
        self.position_history = {}
        
        # ROI and entry/exit direction configurations per camera
        self.roi_settings = {}
        
        # Global control
        self.is_running = False
        
        # Resource monitoring
        self.cpu_usage_history = deque(maxlen=30)  # Keep last 30 readings
        self.memory_usage_history = deque(maxlen=30)
        self.last_resource_check = 0
        self.resource_check_interval = 1.0  # Check every second
        
        # Load YOLOv8 model - shared across all cameras
        self._load_model()
        
        # Load ROI settings for all cameras from database
        self._load_roi_settings()
        
        self.logger.info("Multi-camera DetectionManager initialized")
    
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
        Start detection on all cameras (API compatibility method)
        """
        self.logger.info("Detection start requested via API")
        return self.start_all()
    
    def stop(self):
        """
        Stop detection on all cameras (API compatibility method)
        """
        self.logger.info("Detection stop requested via API")
        return self.stop_all()
    
    def start_all(self):
        """
        Start detection for all cameras
        """
        if self.is_running:
            self.logger.warning("Detection already running")
            return
        
        if self.model is None:
            self.logger.error("Cannot start detection: YOLOv8 model not loaded")
            return
        
        self.is_running = True
        cameras = self.camera_registry.get_active_cameras()
        
        for camera_id, camera in cameras.items():
            self.start_camera(camera_id)
        
        self.logger.info(f"Started detection on {len(cameras)} cameras")
    
    def start_camera(self, camera_id):
        """
        Start detection for a specific camera
        
        Args:
            camera_id: ID of the camera to start detection for
        """
        camera = self.camera_registry.get_camera(camera_id)
        if not camera:
            self.logger.error(f"Cannot start detection: Camera {camera_id} not found")
            return
        
        if not camera.is_running:
            self.logger.info(f"Starting camera {camera_id} first")
            camera.start()
        
        # Check if we already have a thread for this camera
        if camera_id in self.detection_threads and self.detection_threads[camera_id].is_alive():
            self.logger.warning(f"Detection already running for camera {camera_id}")
            return
        
        # Initialize state for this camera if it doesn't exist
        if camera_id not in self.states:
            self.states[camera_id] = {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.DIRECTION_UNKNOWN,
                "no_person_counter": 0
            }
        
        # Initialize position history for direction tracking
        if camera_id not in self.position_history:
            self.position_history[camera_id] = deque(maxlen=20)
        
        # Start a detection thread for this camera
        thread = threading.Thread(
            target=self._run_detection_for_camera,
            args=(camera_id,),
            name=f"detection-{camera_id}"
        )
        thread.daemon = True
        thread.start()
        
        self.detection_threads[camera_id] = thread
        self.logger.info(f"Detection started for camera {camera_id}")
    
    def stop_all(self):
        """
        Stop detection for all cameras
        """
        self.is_running = False
        
        # Wait for all threads to stop
        for camera_id, thread in list(self.detection_threads.items()):
            if thread.is_alive():
                thread.join(timeout=1.0)
            
            # Reset detection state
            if camera_id in self.states:
                self.states[camera_id] = {
                    "person_detected": False,
                    "last_detection_time": None,
                    "current_direction": self.DIRECTION_UNKNOWN,
                    "no_person_counter": 0
                }
            
            # Clear position history
            if camera_id in self.position_history:
                self.position_history[camera_id].clear()
        
        self.detection_threads.clear()
        self.logger.info("Detection stopped for all cameras")
    
    def stop_camera(self, camera_id):
        """
        Stop detection for a specific camera
        
        Args:
            camera_id: ID of the camera to stop detection for
        """
        if camera_id not in self.detection_threads:
            self.logger.warning(f"No detection running for camera {camera_id}")
            return
        
        # Mark thread for stopping
        # The thread will check self.is_running and self.camera_registry.get_camera(camera_id).is_running
        thread = self.detection_threads[camera_id]
        
        # Get the camera
        camera = self.camera_registry.get_camera(camera_id)
        if camera:
            # Set a flag on the camera to stop detection
            camera._stop_detection = True
        
        # Wait for the thread to stop
        if thread.is_alive():
            thread.join(timeout=1.0)
        
        # Reset detection state
        if camera_id in self.states:
            self.states[camera_id] = {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.DIRECTION_UNKNOWN,
                "no_person_counter": 0
            }
        
        # Clear position history
        if camera_id in self.position_history:
            self.position_history[camera_id].clear()
        
        # Remove the thread reference
        del self.detection_threads[camera_id]
        
        if camera:
            # Clear the flag
            camera._stop_detection = False
        
        self.logger.info(f"Detection stopped for camera {camera_id}")
    
    def _run_detection_for_camera(self, camera_id):
        """
        Run detection loop for a specific camera
        
        Args:
            camera_id: ID of the camera to run detection for
        """
        camera = self.camera_registry.get_camera(camera_id)
        if not camera:
            self.logger.error(f"Camera {camera_id} not available for detection")
            return
        
        self.logger.info(f"Detection thread started for camera {camera_id}")
        
        # Set up frame rate control
        frame_interval_idle = 1.0 / self.idle_fps if self.idle_fps > 0 else 1.0
        frame_interval_active = 1.0 / self.active_fps if self.active_fps > 0 else 0.2
        
        last_frame_time = 0
        
        # Check if we have a state for this camera
        if camera_id not in self.states:
            self.states[camera_id] = {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.DIRECTION_UNKNOWN,
                "no_person_counter": 0
            }
        
        # Detection loop
        while self.is_running and camera.is_running and not getattr(camera, '_stop_detection', False):
            try:
                # Check system resources
                self._check_system_resources()
                
                # Get current state for this camera
                state = self.states[camera_id]
                
                # Determine processing rate
                is_person_detected = state["person_detected"]
                current_interval = frame_interval_active if is_person_detected else frame_interval_idle
                
                # Apply resource-based adjustments to frame rate
                adjusted_interval = self._adjust_interval_based_on_resources(current_interval, camera_id)
                
                # Check if it's time to process the next frame
                current_time = time.time()
                if current_time - last_frame_time < adjusted_interval:
                    time.sleep(0.01)  # Small sleep to avoid busy waiting
                    continue
                
                last_frame_time = current_time
                
                # Get the latest frame
                frame = camera.get_latest_frame()
                if frame is None:
                    # No frame available, sleep and try again
                    time.sleep(0.1)
                    continue
                
                # Process the frame
                self._process_frame(frame, camera_id)
                
            except Exception as e:
                self.logger.error(f"Error in detection loop for camera {camera_id}: {e}")
                time.sleep(0.5)
        
        self.logger.info(f"Detection thread stopped for camera {camera_id}")
    
    def _process_frame(self, frame, camera_id):
        """
        Process a single frame for a specific camera
        
        Args:
            frame: The frame to process
            camera_id: ID of the camera this frame is from
        """
        if self.model is None:
            return
        
        # Run YOLOv8 inference
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        
        # Check if any person is detected
        person_found = False
        bbox_center_x = None
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Check if detection is a person
                cls = int(box.cls[0])
                if cls == self.person_class_id:
                    # Get bounding box: x1, y1, x2, y2
                    xyxy = box.xyxy[0].cpu().numpy()
                    
                    # Calculate center point
                    center_x = (xyxy[0] + xyxy[2]) / 2
                    center_y = (xyxy[1] + xyxy[3]) / 2
                    
                    # Check if person is within ROI if ROI is set for this camera
                    if camera_id in self.roi_settings and "coords" in self.roi_settings[camera_id]:
                        rx1, ry1, rx2, ry2 = self.roi_settings[camera_id]["coords"]
                        
                        # Skip if person is outside ROI
                        if not (rx1 <= center_x <= rx2 and ry1 <= center_y <= ry2):
                            continue
                    
                    person_found = True
                    bbox_center_x = center_x
                    break
                
            if person_found:
                break
        
        # Update detection state for this camera
        self._update_detection_state(camera_id, person_found, frame, bbox_center_x)
    
    def _save_snapshot(self, camera_id, frame):
        """
        Save a snapshot image
        
        Args:
            camera_id: ID of the camera
            frame: The frame to save
            
        Returns:
            str: Path to the saved snapshot
        """
        SNAPSHOT_DIR = "snapshots"
        
        # Create snapshots directory if it doesn't exist
        if not os.path.exists(SNAPSHOT_DIR):
            os.makedirs(SNAPSHOT_DIR)
            
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{SNAPSHOT_DIR}/camera_{camera_id}_{timestamp}.jpg"
        
        # Save the image
        cv2.imwrite(filename, frame)
        self.logger.info(f"Snapshot saved: {filename}")
        
        return filename
    
    def _update_detection_state(self, camera_id, person_present, frame, center_x):
        """
        Update detection state for a specific camera
        
        Args:
            camera_id: ID of the camera
            person_present: Whether a person is present in the frame
            frame: The current frame
            center_x: X-coordinate of the person's bounding box center (or None)
        """
        if camera_id not in self.states:
            self.states[camera_id] = {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.DIRECTION_UNKNOWN,
                "no_person_counter": 0
            }
        
        state = self.states[camera_id]
        
        if person_present:
            if not state["person_detected"]:
                # Person has just appeared
                state["person_detected"] = True
                state["last_detection_time"] = time.time()
                state["current_direction"] = self.DIRECTION_UNKNOWN
                state["no_person_counter"] = 0
                
                # Save snapshot when person is first detected
                snapshot_path = self._save_snapshot(camera_id, frame)
                
                # Record the detection in dashboard
                if self.dashboard_manager:
                    self.dashboard_manager.record_detection(camera_id=camera_id)
                
                # Log detection event in database
                if self.db_manager:
                    self.db_manager.log_detection_event(
                        "detection_start", 
                        camera_id=camera_id
                    )
                
                # Emit event via API manager
                if self.api_manager:
                    self.api_manager.emit_event(
                        "detection_start", 
                        {"camera": camera_id}
                    )
                
                self.logger.info(f"Person detected on camera {camera_id}")
            
            # Track position for direction detection
            if center_x is not None:
                self._record_position(camera_id, center_x)
        else:
            # No person detected in this frame
            if state["person_detected"]:
                # Increment the counter for consecutive frames without a person
                state["no_person_counter"] += 1
                
                # If no person for several consecutive frames, consider the person gone
                if state["no_person_counter"] >= 5:
                    # Person has disappeared
                    state["person_detected"] = False
                    
                    # Save snapshot when person is no longer detected
                    snapshot_path = self._save_snapshot(camera_id, frame)
                    
                    # Get direction string
                    direction_str = self._get_direction_string(camera_id)
                    
                    # Determine if this was an entry or exit based on direction and configuration
                    event_type = "detection_end"
                    if camera_id in self.roi_settings and "entry_direction" in self.roi_settings[camera_id]:
                        entry_dir = self.roi_settings[camera_id]["entry_direction"]
                        if direction_str == "left_to_right":
                            event_type = "entry" if entry_dir == "LTR" else "exit"
                        elif direction_str == "right_to_left":
                            event_type = "entry" if entry_dir == "RTL" else "exit"
                    
                    # Log direction in dashboard
                    if self.dashboard_manager:
                        if direction_str != "unknown":
                            self.dashboard_manager.record_direction(direction_str, camera_id=camera_id)
                        
                        # Log footfall
                        self.dashboard_manager.record_footfall(event_type, camera_id=camera_id)
                    
                    # Log detection end event in database
                    if self.db_manager:
                        self.db_manager.log_detection_event(
                            event_type, 
                            direction=direction_str,
                            camera_id=camera_id
                        )
                    
                    # Emit event via API manager
                    if self.api_manager:
                        self.api_manager.emit_event(
                            event_type, 
                            {
                                "camera": camera_id,
                                "event": event_type,
                                "direction": direction_str
                            }
                        )
                    
                    self.logger.info(f"Person no longer detected on camera {camera_id}, direction: {direction_str}, event: {event_type}")
    
    def _record_position(self, camera_id, center_x):
        """
        Record the position of a person for direction tracking
        
        Args:
            camera_id: ID of the camera
            center_x: X-coordinate of the person's bounding box center
        """
        # Ensure we have a position history for this camera
        if camera_id not in self.position_history:
            self.position_history[camera_id] = deque(maxlen=20)
        
        # Add current position to history
        self.position_history[camera_id].append((time.time(), center_x))
        
        # Update direction if we have enough positions
        if len(self.position_history[camera_id]) >= 3:
            self._update_direction(camera_id)
    
    def _update_direction(self, camera_id):
        """
        Update the movement direction based on position history
        
        Args:
            camera_id: ID of the camera
        """
        if camera_id not in self.states or camera_id not in self.position_history:
            return
        
        # Get the oldest and newest positions
        if len(self.position_history[camera_id]) < 3:
            return
        
        # Use the oldest and newest positions for more stable direction detection
        oldest_time, oldest_x = self.position_history[camera_id][0]
        newest_time, newest_x = self.position_history[camera_id][-1]
        
        # Calculate time difference to ensure valid movement
        time_diff = newest_time - oldest_time
        if time_diff <= 0.1:  # Require at least 0.1 seconds between samples
            return
        
        # Calculate movement
        movement = newest_x - oldest_x
        
        # Only update direction if movement exceeds threshold
        if abs(movement) >= self.direction_threshold:
            prev_direction = self.states[camera_id]["current_direction"]
            
            # Determine new direction
            new_direction = (
                self.DIRECTION_LEFT_TO_RIGHT if movement > 0 
                else self.DIRECTION_RIGHT_TO_LEFT
            )
            
            # Update state if direction changed
            if prev_direction != new_direction:
                self.states[camera_id]["current_direction"] = new_direction
                
                # Log direction change
                direction_str = self._direction_to_string(new_direction)
                self.logger.info(f"Direction updated for camera {camera_id}: {direction_str}")
                
                # Emit direction event via API manager
                if self.api_manager:
                    self.api_manager.emit_event(
                        "direction", 
                        {
                            "camera": camera_id,
                            "direction": direction_str
                        }
                    )
    
    def _direction_to_string(self, direction):
        """
        Convert direction constant to string
        
        Args:
            direction: Direction constant
            
        Returns:
            str: Direction string
        """
        if direction == self.DIRECTION_LEFT_TO_RIGHT:
            return "left_to_right"
        elif direction == self.DIRECTION_RIGHT_TO_LEFT:
            return "right_to_left"
        else:
            return "unknown"
    
    def _get_direction_string(self, camera_id):
        """
        Get the current direction string for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            str: Direction string
        """
        if camera_id in self.states:
            return self._direction_to_string(self.states[camera_id]["current_direction"])
        return "unknown"
    
    def _check_system_resources(self):
        """
        Check system CPU and memory usage
        """
        current_time = time.time()
        
        # Only check periodically to avoid overhead
        if current_time - self.last_resource_check < self.resource_check_interval:
            return
        
        self.last_resource_check = current_time
        
        try:
            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Add to history
            self.cpu_usage_history.append(cpu_percent)
            self.memory_usage_history.append(memory_percent)
            
            # Log high resource usage
            if cpu_percent > 90:
                self.logger.warning(f"High CPU usage: {cpu_percent}%")
            if memory_percent > 90:
                self.logger.warning(f"High memory usage: {memory_percent}%")
                
        except Exception as e:
            self.logger.error(f"Error checking system resources: {e}")
    
    def _adjust_interval_based_on_resources(self, base_interval, camera_id):
        """
        Adjust processing interval based on system resources and camera priority
        
        Args:
            base_interval: Base interval in seconds
            camera_id: Camera ID for priority consideration
            
        Returns:
            float: Adjusted interval
        """
        # If we don't have enough history yet, use base interval
        if len(self.cpu_usage_history) < 5:
            return base_interval
        
        # Calculate average CPU usage
        avg_cpu = sum(self.cpu_usage_history) / len(self.cpu_usage_history)
        
        # Adjust based on CPU load
        if avg_cpu > 80:
            # High load, increase interval (slow down)
            # Prioritize main camera if load is high
            if camera_id == "main":
                # Main camera gets less slowdown
                return base_interval * 1.2
            else:
                # Secondary cameras get more slowdown
                return base_interval * 2.0
        elif avg_cpu > 60:
            # Moderate load
            if camera_id == "main":
                return base_interval * 1.1
            else:
                return base_interval * 1.5
        else:
            # Normal load, use base interval
            return base_interval
    
    def get_detection_status(self, camera_id=None):
        """
        Get the current detection status
        
        Args:
            camera_id: Optional ID of the camera to get status for
            
        Returns:
            dict: Detection status
        """
        if camera_id:
            # Return status for a specific camera
            if camera_id in self.states:
                state = self.states[camera_id]
                return {
                    "camera_id": camera_id,
                    "person_detected": state["person_detected"],
                    "last_detection_time": state["last_detection_time"],
                    "direction": self._direction_to_string(state["current_direction"])
                }
            else:
                return {
                    "camera_id": camera_id,
                    "person_detected": False,
                    "last_detection_time": None,
                    "direction": "unknown"
                }
        else:
            # Return status for all cameras
            result = {}
            for cam_id in self.states:
                result[cam_id] = self.get_detection_status(cam_id)
            return result
    
    def is_person_detected(self, camera_id=None):
        """
        Check if a person is detected
        
        Args:
            camera_id: Optional ID of the camera to check
            
        Returns:
            bool: True if a person is detected, False otherwise
        """
        if camera_id:
            # Check specific camera
            if camera_id in self.states:
                return self.states[camera_id]["person_detected"]
            return False
        else:
            # Check any camera
            for camera_id in self.states:
                if self.states[camera_id]["person_detected"]:
                    return True
            return False
    
    def get_active_cameras(self):
        """
        Get all cameras with active detection
        
        Returns:
            list: List of camera IDs with active detection
        """
        return list(self.detection_threads.keys())
    
    def get_detection_count(self):
        """
        Get the number of active detection threads
        
        Returns:
            int: Number of active detection threads
        """
        return len(self.detection_threads)
    
    def get_system_resources(self):
        """
        Get current system resource usage
        
        Returns:
            dict: System resource information
        """
        return {
            "cpu_percent": list(self.cpu_usage_history),
            "memory_percent": list(self.memory_usage_history),
            "avg_cpu": sum(self.cpu_usage_history) / len(self.cpu_usage_history) if self.cpu_usage_history else 0,
            "avg_memory": sum(self.memory_usage_history) / len(self.memory_usage_history) if self.memory_usage_history else 0
        }
    
    def _load_roi_settings(self):
        """
        Load ROI and entry direction settings from database for all cameras
        """
        if not self.db_manager:
            self.logger.warning("No database manager available for loading ROI settings")
            return
        
        try:
            # Get ROI settings for all cameras
            cameras = self.camera_registry.get_all_cameras()
            
            for camera_id in cameras:
                roi_data = self.db_manager.get_camera_roi(camera_id)
                
                if roi_data:
                    x1, y1, x2, y2 = roi_data.get('coords', (None, None, None, None))
                    entry_direction = roi_data.get('entry_direction')
                    
                    if all(coord is not None for coord in (x1, y1, x2, y2)) and entry_direction:
                        self.roi_settings[camera_id] = {
                            "coords": (x1, y1, x2, y2),
                            "entry_direction": entry_direction
                        }
                        self.logger.info(f"Loaded ROI settings for camera {camera_id}: "
                                       f"({x1}, {y1}, {x2}, {y2}), entry: {entry_direction}")
            
        except Exception as e:
            self.logger.error(f"Error loading ROI settings: {e}")
    
    def set_roi(self, camera_id, roi_coords):
        """
        Set ROI for a specific camera
        
        Args:
            camera_id: ID of the camera
            roi_coords: Tuple of (x1, y1, x2, y2) coordinates
            
        Returns:
            bool: True if set successfully, False otherwise
        """
        try:
            # Check if the camera exists
            if not self.camera_registry.get_camera(camera_id):
                self.logger.error(f"Cannot set ROI: Camera {camera_id} not found")
                return False
                
            # Validate ROI coordinates
            if len(roi_coords) != 4:
                self.logger.error(f"Invalid ROI coordinates: {roi_coords}")
                return False
                
            # Get existing entry direction if available
            entry_direction = None
            if camera_id in self.roi_settings:
                entry_direction = self.roi_settings[camera_id].get("entry_direction", self.ENTRY_DIRECTION_LTR)
            else:
                entry_direction = self.ENTRY_DIRECTION_LTR
                
            # Update ROI settings
            self.roi_settings[camera_id] = {
                "coords": roi_coords,
                "entry_direction": entry_direction
            }
            
            # Save to database if available
            if self.db_manager:
                self.db_manager.save_camera_roi(camera_id, roi_coords, entry_direction)
                
            self.logger.info(f"Set ROI for camera {camera_id}: {roi_coords}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting ROI for camera {camera_id}: {e}")
            return False
    
    def set_entry_direction(self, camera_id, entry_direction):
        """
        Set entry direction for a specific camera
        
        Args:
            camera_id: ID of the camera
            entry_direction: Entry direction (LTR or RTL)
            
        Returns:
            bool: True if set successfully, False otherwise
        """
        try:
            # Check if the camera exists
            if not self.camera_registry.get_camera(camera_id):
                self.logger.error(f"Cannot set entry direction: Camera {camera_id} not found")
                return False
                
            # Validate entry direction
            if entry_direction not in (self.ENTRY_DIRECTION_LTR, self.ENTRY_DIRECTION_RTL):
                self.logger.error(f"Invalid entry direction: {entry_direction}")
                return False
                
            # Get existing ROI if available
            roi_coords = None
            if camera_id in self.roi_settings:
                roi_coords = self.roi_settings[camera_id].get("coords")
                
            # Update entry direction
            if camera_id not in self.roi_settings:
                self.roi_settings[camera_id] = {}
                
            self.roi_settings[camera_id]["entry_direction"] = entry_direction
            
            # Save to database if available
            if self.db_manager and roi_coords:
                self.db_manager.save_camera_roi(camera_id, roi_coords, entry_direction)
                
            self.logger.info(f"Set entry direction for camera {camera_id}: {entry_direction}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting entry direction for camera {camera_id}: {e}")
            return False
    
    def get_roi(self, camera_id):
        """
        Get ROI for a specific camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            tuple: ROI coordinates (x1, y1, x2, y2) or None
        """
        if camera_id in self.roi_settings:
            return self.roi_settings[camera_id].get("coords")
        return None
    
    def get_entry_direction(self, camera_id):
        """
        Get entry direction for a specific camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            str: Entry direction or None
        """
        if camera_id in self.roi_settings:
            return self.roi_settings[camera_id].get("entry_direction")
        return None
    
    def clear_roi(self, camera_id):
        """
        Clear ROI for a specific camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            bool: True if cleared successfully, False otherwise
        """
        try:
            # Check if the camera exists
            if not self.camera_registry.get_camera(camera_id):
                self.logger.error(f"Cannot clear ROI: Camera {camera_id} not found")
                return False
                
            # Remove ROI settings
            if camera_id in self.roi_settings:
                del self.roi_settings[camera_id]
                
            # Delete from database if available
            if self.db_manager:
                self.db_manager.delete_camera_roi(camera_id)
                
            self.logger.info(f"Cleared ROI for camera {camera_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error clearing ROI for camera {camera_id}: {e}")
            return False 