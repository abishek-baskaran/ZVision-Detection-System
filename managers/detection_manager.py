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
    DIRECTION_BOTTOM_TO_TOP = 3
    DIRECTION_TOP_TO_BOTTOM = 4
    DIRECTION_DIAGONAL_BL_TR = 5  # bottom-left to top-right
    DIRECTION_DIAGONAL_BR_TL = 6  # bottom-right to top-left
    DIRECTION_DIAGONAL_TL_BR = 7  # top-left to bottom-right
    DIRECTION_DIAGONAL_TR_BL = 8  # top-right to bottom-left
    DIRECTION_INWARD = 9          # moving toward center (growing)
    DIRECTION_OUTWARD = 10        # moving away from center (shrinking)
    
    # Entry/Exit direction mapping constants
    ENTRY_DIRECTION_LTR = "LTR"  # Left-to-right is entry
    ENTRY_DIRECTION_RTL = "RTL"  # Right-to-left is entry
    ENTRY_DIRECTION_BTT = "BTT"  # Bottom-to-top is entry
    ENTRY_DIRECTION_TTB = "TTB"  # Top-to-bottom is entry
    ENTRY_DIRECTION_BL_TR = "BLTR"  # Bottom-left to top-right is entry
    ENTRY_DIRECTION_BR_TL = "BRTL"  # Bottom-right to top-left is entry
    ENTRY_DIRECTION_TL_BR = "TLBR"  # Top-left to bottom-right is entry
    ENTRY_DIRECTION_TR_BL = "TRBL"  # Top-right to bottom-left is entry
    ENTRY_DIRECTION_IN = "IN"     # Moving inward is entry
    ENTRY_DIRECTION_OUT = "OUT"   # Moving outward is entry
    
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
        self.direction_threshold_ratio = detection_config.get('direction_threshold_ratio', 0.1)
        
        # Dictionary to hold detection threads and states for each camera
        self.detection_threads = {}
        self.states = {}
        self.position_history = {}
        
        # Track states for ByteTrack object tracking
        self.track_states = {}  # camera_id -> {track_id -> track_info}
        
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
                "no_person_counter": 0,
                "last_snapshot_time": 0,  # Track last snapshot time
                "snapshot_interval": 1.0  # Take snapshot every 1 second
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
                    "no_person_counter": 0,
                    "last_snapshot_time": 0,  # Track last snapshot time
                    "snapshot_interval": 1.0  # Take snapshot every 1 second
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
                "no_person_counter": 0,
                "last_snapshot_time": 0,  # Track last snapshot time
                "snapshot_interval": 1.0  # Take snapshot every 1 second
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
                "no_person_counter": 0,
                "last_snapshot_time": 0,  # Track last snapshot time
                "snapshot_interval": 1.0  # Take snapshot every 1 second
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
        
        # Get frame dimensions for proper ROI scaling
        frame_height, frame_width = frame.shape[:2]
        
        # Check if ROI is set for this camera
        roi_frame = frame
        has_roi = False
        rx1, ry1, rx2, ry2 = 0, 0, frame_width, frame_height  # Initialize for offset calculation
        if camera_id in self.roi_settings and "coords" in self.roi_settings[camera_id]:
            # Get ROI coordinates
            roi_coords = self.roi_settings[camera_id]["coords"]
            
            # Validate that all coordinates exist and are valid
            if roi_coords and len(roi_coords) == 4 and all(coord is not None for coord in roi_coords):
                # Convert ROI coordinates to numeric values (handle potential strings)
                rx1 = float(roi_coords[0])
                ry1 = float(roi_coords[1])
                rx2 = float(roi_coords[2])
                ry2 = float(roi_coords[3])
                
                # Default 320x240 canvas size used in frontend
                canvas_width = 320
                canvas_height = 240
                
                # Scale ROI coordinates from canvas to frame if needed
                if frame_width > 1.5 * canvas_width:  # Only scale if frame is significantly larger
                    scale_x = frame_width / canvas_width
                    scale_y = frame_height / canvas_height
                    rx1 = rx1 * scale_x
                    ry1 = ry1 * scale_y
                    rx2 = rx2 * scale_x
                    ry2 = ry2 * scale_y
                
                # Make sure coordinates are in valid range
                rx1 = max(0, min(rx1, frame_width))
                ry1 = max(0, min(ry1, frame_height))
                rx2 = max(0, min(rx2, frame_width))
                ry2 = max(0, min(ry2, frame_height))
                
                # Convert to integers
                rx1, ry1, rx2, ry2 = int(rx1), int(ry1), int(rx2), int(ry2)
                
                # Crop the frame to the ROI
                roi_frame = frame[ry1:ry2, rx1:rx2]
                self.logger.debug(f"Cropped frame for camera {camera_id} from {frame.shape} to {roi_frame.shape}")
                has_roi = True
                
                # If the ROI is empty or invalid, use the original frame
                if roi_frame.size == 0:
                    self.logger.warning(f"ROI resulted in empty frame for camera {camera_id}, using original frame")
                    roi_frame = frame
                    has_roi = False
                    rx1, ry1 = 0, 0
                    rx2, ry2 = frame_width, frame_height
            else:
                self.logger.warning(f"Invalid ROI coordinates for camera {camera_id}: {roi_coords}")
                rx2, ry2 = frame_width, frame_height
        
        # Run YOLOv8 inference with ByteTrack tracking
        results = self.model.track(roi_frame, conf=self.confidence_threshold, verbose=False, tracker="bytetrack.yaml")
        
        # Initialize variables for detection state
        any_person_found = False
        
        # Check if camera_id exists in track_states
        if camera_id not in self.track_states:
            self.track_states[camera_id] = {}
        
        # Current time for tracking
        current_time = time.time()
        
        # Track IDs seen in this frame
        track_ids_seen = set()
        
        # Process each detection result
        for r in results:
            if not hasattr(r, 'boxes') or not hasattr(r.boxes, 'id'):
                continue  # Skip if no tracking IDs available
                
            boxes = r.boxes
            for i, box in enumerate(boxes):
                # Check if detection is a person
                cls = int(box.cls[0])
                if cls == self.person_class_id:
                    # Get tracking ID
                    if box.id is None:
                        continue  # Skip if no tracking ID
                        
                    track_id = int(box.id[0])
                    track_ids_seen.add(track_id)
                    
                    # Get bounding box: x1, y1, x2, y2
                    xyxy = box.xyxy[0].cpu().numpy()
                    
                    # Calculate center point
                    center_x = (xyxy[0] + xyxy[2]) / 2
                    center_y = (xyxy[1] + xyxy[3]) / 2
                    
                    # If using ROI, adjust center coordinates to the original frame coordinates
                    if has_roi:
                        center_x = center_x + rx1
                        center_y = center_y + ry1
                    
                    # Person found
                    any_person_found = True
                    
                    # Update track state and check for movement direction
                    self._update_track_state(camera_id, track_id, center_x, center_y, rx1, ry1, rx2, ry2, frame, current_time)
        
        # Remove expired tracks (not seen for 2 seconds)
        expired_tracks = []
        for track_id, track_info in self.track_states[camera_id].items():
            if track_id not in track_ids_seen:
                # Track not seen in this frame
                if current_time - track_info['last_seen'] > 2.0:
                    # Track expired
                    expired_tracks.append(track_id)
        
        # Remove expired tracks
        for track_id in expired_tracks:
            del self.track_states[camera_id][track_id]
        
        # Update overall detection state for this camera
        self._update_detection_state(camera_id, any_person_found, frame)
    
    def _update_track_state(self, camera_id, track_id, center_x, center_y, roi_x1, roi_y1, roi_x2, roi_y2, frame, current_time):
        """
        Update the state of a tracked object and check for movement direction
        
        Args:
            camera_id: ID of the camera
            track_id: ID of the tracked object
            center_x: X-coordinate of the object's center
            center_y: Y-coordinate of the object's center
            roi_x1, roi_y1, roi_x2, roi_y2: ROI coordinates in original frame
            frame: Current video frame
            current_time: Current timestamp
        """
        # Check if point is in ROI - no longer returning early to allow for boundary crossing detection
        in_roi = (roi_x1 <= center_x <= roi_x2) and (roi_y1 <= center_y <= roi_y2)
        
        # Get track info if it exists
        if track_id not in self.track_states[camera_id]:
            # New track
            self.track_states[camera_id][track_id] = {
                'positions': deque(maxlen=10),  # Store last 10 positions for direction calculation
                'last_seen': current_time,
                'direction_computed': False,    # Whether we've computed a direction yet
                'movement_direction': None,     # 'entry', 'exit', or None
                'first_seen': current_time,
                'snapshot_path': None,          # Store a single snapshot path instead of a list
                'in_roi': in_roi,              # Track whether object is in ROI
                'roi_status_changed': False,    # Track if ROI status changed
                'direction_logged': False       # Track if direction event already logged
            }
            
            # Add first position
            self.track_states[camera_id][track_id]['positions'].append((center_x, center_y))
            
            # Take initial snapshot - only one per track_id
            snapshot_path = self._save_snapshot(camera_id, frame)
            self.track_states[camera_id][track_id]['snapshot_path'] = snapshot_path
            
            # Don't log detection_start event to database anymore
            # Only emit event via API manager for notification purposes
            if self.api_manager:
                self.api_manager.emit_event(
                    "detection_start",
                    {"camera": camera_id, "track_id": track_id}
                )
            
            self.logger.info(f"New track {track_id} detected on camera {camera_id}")
        else:
            # Existing track - update position history
            track_info = self.track_states[camera_id][track_id]
            prev_in_roi = track_info['in_roi']
            
            # Check for ROI boundary crossing
            if in_roi != prev_in_roi:
                # ROI boundary crossing detected
                if in_roi:
                    # Entering ROI - log entry event but only if not already logged by direction
                    if not track_info.get('direction_logged', False) or track_info.get('movement_direction') != 'entry':
                        self._log_direction_event(camera_id, track_id, "entry", frame)
                        self.logger.info(f"Track {track_id} entered ROI on camera {camera_id}")
                        track_info['direction_logged'] = True
                        track_info['movement_direction'] = 'entry'
                else:
                    # Exiting ROI - log exit event but only if not already logged by direction
                    if not track_info.get('direction_logged', False) or track_info.get('movement_direction') != 'exit':
                        self._log_direction_event(camera_id, track_id, "exit", frame)
                        self.logger.info(f"Track {track_id} exited ROI on camera {camera_id}")
                        track_info['direction_logged'] = True
                        track_info['movement_direction'] = 'exit'
                
                track_info['roi_status_changed'] = True
            
            # Update position history
            track_info['positions'].append((center_x, center_y))
            
            # Calculate movement direction if we have enough positions and haven't logged a direction yet
            # or if we've crossed an ROI boundary and want to recalculate
            direction_check_needed = ((len(track_info['positions']) >= 3 and not track_info.get('direction_logged', False))
                                     or track_info['roi_status_changed'])
            
            if direction_check_needed:
                movement_vector = self._calculate_movement_vector(track_info['positions'])
                if movement_vector:
                    direction = self._determine_direction(camera_id, movement_vector)
                    if direction and not track_info.get('direction_logged', False):
                        # Log direction event - this is the key change, removing comment
                        self._log_direction_event(camera_id, track_id, direction, frame)
                        
                        track_info['direction_computed'] = True
                        track_info['movement_direction'] = direction
                        track_info['direction_logged'] = True
                        self.logger.info(f"Track {track_id} movement direction {direction} on camera {camera_id}")
                        track_info['roi_status_changed'] = False
            
            # Remove logging of detection_continuing events
            # We'll still update the track's last_seen time
            
            # Update track info
            track_info.update({
                'last_seen': current_time,
                'last_position': (center_x, center_y),
                'in_roi': in_roi
            })
    
    def _calculate_movement_vector(self, positions):
        """
        Calculate the movement vector from a list of positions
        
        Args:
            positions: List of (x, y) positions
            
        Returns:
            tuple: Normalized movement vector (x, y) or None if can't be determined
        """
        if len(positions) < 3:  # Reduced from 5 to 3 for faster direction detection
            return None
        
        # Use first 30% and last 30% of positions for more robust direction detection
        first_third = max(1, len(positions) // 3)
        start_points = list(positions)[:first_third]
        end_points = list(positions)[-first_third:]
        
        # Calculate average positions
        start_x_avg = sum(p[0] for p in start_points) / len(start_points)
        start_y_avg = sum(p[1] for p in start_points) / len(start_points)
        end_x_avg = sum(p[0] for p in end_points) / len(end_points)
        end_y_avg = sum(p[1] for p in end_points) / len(end_points)
        
        # Calculate movement vector
        movement_x = end_x_avg - start_x_avg
        movement_y = end_y_avg - start_y_avg
        
        # Calculate magnitude of movement
        magnitude = (movement_x**2 + movement_y**2)**0.5
        
        # Check if movement is significant (reduced from 5.0 to 2.0 pixels)
        if magnitude < 2.0:  # Reduced threshold for more sensitive direction detection
            return None
        
        # Normalize the vector
        if magnitude > 1e-6:  # Avoid division by zero
            movement_x /= magnitude
            movement_y /= magnitude
        
        return (movement_x, movement_y)
    
    def _determine_direction(self, camera_id, movement_vector):
        """
        Determine if movement is entry or exit based on camera direction vector
        
        Args:
            camera_id: ID of the camera
            movement_vector: Normalized movement vector (x, y)
            
        Returns:
            str: 'entry', 'exit', or None if direction can't be determined
        """
        if movement_vector is None or camera_id not in self.roi_settings:
            return None
        
        # Get camera direction vector
        direction = self.roi_settings[camera_id].get("entry_direction", "1,0")
        
        # Parse direction vector
        try:
            if ',' in direction:
                # New vector format "x,y"
                dir_x, dir_y = map(float, direction.split(','))
            else:
                # Legacy format (LTR, RTL, etc.)
                if direction == "LTR":
                    dir_x, dir_y = 1, 0
                elif direction == "RTL":
                    dir_x, dir_y = -1, 0
                elif direction == "BTT":
                    dir_x, dir_y = 0, -1
                elif direction == "TTB":
                    dir_x, dir_y = 0, 1
                elif direction == "BLTR":
                    dir_x, dir_y = 1, -1
                elif direction == "BRTL":
                    dir_x, dir_y = -1, -1
                elif direction == "TLBR":
                    dir_x, dir_y = 1, 1
                elif direction == "TRBL":
                    dir_x, dir_y = -1, 1
                else:
                    dir_x, dir_y = 1, 0  # Default to right
            
            # Normalize direction vector
            magnitude = (dir_x**2 + dir_y**2)**0.5
            if magnitude > 1e-6:
                dir_x /= magnitude
                dir_y /= magnitude
            
            self.logger.debug(f"Camera {camera_id} direction vector: ({dir_x}, {dir_y})")
            self.logger.debug(f"Movement vector: ({movement_vector[0]}, {movement_vector[1]})")
            
            # Calculate dot product
            dot_product = movement_vector[0] * dir_x + movement_vector[1] * dir_y
            
            self.logger.debug(f"Dot product: {dot_product}")
            
            # Apply threshold - reduced from 0.3 to 0.2 for more sensitive detection
            threshold = 0.2  # Reduced dot product threshold
            if dot_product > threshold:
                return "entry"
            elif dot_product < -threshold:
                return "exit"
            else:
                return None  # Movement perpendicular to direction
        except Exception as e:
            self.logger.error(f"Error determining direction: {e}")
            return None
    
    def _log_direction_event(self, camera_id, track_id, event_type, frame):
        """
        Log a direction event (entry or exit)
        
        Args:
            camera_id: ID of the camera
            track_id: ID of the tracked object
            event_type: 'entry' or 'exit'
            frame: Current video frame
        """
        self.logger.info(f"Direction detected: {event_type} for track {track_id} on camera {camera_id}")
        
        # Use existing snapshot instead of creating a new one
        snapshot_path = self.track_states[camera_id][track_id]['snapshot_path']
        
        # Log direction in dashboard
        if self.dashboard_manager:
            # Record footfall
            self.dashboard_manager.record_footfall(event_type, camera_id=camera_id)
        
        # Log entry/exit events in database (keep this part)
        if self.db_manager and (event_type == 'entry' or event_type == 'exit'):
            self.db_manager.log_detection_event(
                event_type,
                camera_id=camera_id,
                snapshot_path=snapshot_path,
                details=f"track_id:{track_id}"
            )
        
        # Emit event via API manager
        if self.api_manager:
            self.api_manager.emit_event(
                event_type,
                {
                    "camera": camera_id,
                    "event": event_type,
                    "track_id": track_id
                }
            )
    
    def _update_detection_state(self, camera_id, person_present, frame):
        """
        Update overall detection state for a specific camera
        
        Args:
            camera_id: ID of the camera
            person_present: Whether a person is present in the frame
            frame: The current frame
        """
        if camera_id not in self.states:
            self.states[camera_id] = {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.DIRECTION_UNKNOWN,
                "no_person_counter": 0,
                "last_snapshot_time": 0,  # Track last snapshot time
                "snapshot_interval": 1.0  # Take snapshot every 1 second
            }
        
        state = self.states[camera_id]
        current_time = time.time()
        
        # Update overall state based on person presence
        if person_present:
            # Update person detected state
            if not state["person_detected"]:
                state["person_detected"] = True
                state["last_detection_time"] = current_time
                state["no_person_counter"] = 0
        else:
            # No person detected in this frame
            if state["person_detected"]:
                # Increment the counter for consecutive frames without a person
                state["no_person_counter"] += 1
                
                # If no person for several consecutive frames, consider all people gone
                if state["no_person_counter"] >= 5:
                    state["person_detected"] = False
                    self.logger.info(f"No more persons detected on camera {camera_id}")
    
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
        
        # Create camera-specific directory
        camera_dir = os.path.join(SNAPSHOT_DIR, camera_id)
        if not os.path.exists(camera_dir):
            os.makedirs(camera_dir)
            
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{camera_dir}/snapshot_{timestamp}.jpg"
        
        # Save the image
        cv2.imwrite(filename, frame)
        
        return filename
    
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
            entry_direction: Entry direction (LTR, RTL, BTT, TTB, BLTR, BRTL, TLBR, TRBL, IN, OUT) 
                             or vector format "x,y"
            
        Returns:
            bool: True if set successfully, False otherwise
        """
        try:
            # Check if the camera exists
            if not self.camera_registry.get_camera(camera_id):
                self.logger.error(f"Cannot set entry direction: Camera {camera_id} not found")
                return False
                
            # Validate entry direction
            valid_directions = (
                self.ENTRY_DIRECTION_LTR, self.ENTRY_DIRECTION_RTL, 
                self.ENTRY_DIRECTION_BTT, self.ENTRY_DIRECTION_TTB,
                self.ENTRY_DIRECTION_BL_TR, self.ENTRY_DIRECTION_BR_TL,
                self.ENTRY_DIRECTION_TL_BR, self.ENTRY_DIRECTION_TR_BL,
                self.ENTRY_DIRECTION_IN, self.ENTRY_DIRECTION_OUT
            )
            
            # Check if it's a vector format "x,y"
            is_vector_format = ',' in entry_direction
            
            if not is_vector_format and entry_direction not in valid_directions:
                self.logger.error(f"Invalid entry direction: {entry_direction}")
                return False
            
            # If it's vector format, validate it
            if is_vector_format:
                try:
                    x, y = map(float, entry_direction.split(','))
                    # Normalize the vector
                    magnitude = (x**2 + y**2)**0.5
                    if magnitude < 1e-6:
                        self.logger.error(f"Invalid direction vector (too small): {entry_direction}")
                        return False
                except Exception as e:
                    self.logger.error(f"Invalid direction vector format: {entry_direction} - {e}")
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
        elif direction == self.DIRECTION_BOTTOM_TO_TOP:
            return "bottom_to_top"
        elif direction == self.DIRECTION_TOP_TO_BOTTOM:
            return "top_to_bottom"
        elif direction == self.DIRECTION_DIAGONAL_BL_TR:
            return "bottom_left_to_top_right"
        elif direction == self.DIRECTION_DIAGONAL_BR_TL:
            return "bottom_right_to_top_left"
        elif direction == self.DIRECTION_DIAGONAL_TL_BR:
            return "top_left_to_bottom_right"
        elif direction == self.DIRECTION_DIAGONAL_TR_BL:
            return "top_right_to_bottom_left"
        elif direction == self.DIRECTION_INWARD:
            return "inward"
        elif direction == self.DIRECTION_OUTWARD:
            return "outward"
        else:
            return "unknown" 