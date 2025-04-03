#!/usr/bin/env python3
# Camera Registry - Manages multiple camera instances

import threading
import time
from .camera_manager import CameraManager
import cv2
import os

class CameraRegistry:
    """
    Manages multiple camera instances
    """
    
    def __init__(self, resource_provider, skip_default_init=False):
        """
        Initialize the camera registry
        
        Args:
            resource_provider: The resource provider for config and logging
            skip_default_init: If True, skip initializing default cameras
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.resource_provider = resource_provider
        
        # Dictionary of camera_id -> CameraManager
        self.cameras = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Initialization state tracking
        self.initialized = False
        
        # Load default camera configuration if not skipped
        if not skip_default_init:
            self._init_default_camera()
        
        self.logger.info(f"CameraRegistry initialized with {len(self.cameras)} cameras")
        self.initialized = True
    
    def _init_default_camera(self):
        """
        Initialize the default camera from config
        """
        try:
            # Get camera settings from config
            camera_config = self.config.get('camera', {})
            device_id = camera_config.get('device_id', 0)
            
            # Try to add the default camera
            success = self.add_camera("main", device_id, "Main Camera", True)
            
            # If the default camera didn't work, try alternative indices
            if not success:
                self.logger.warning(f"Failed to initialize camera with device_id={device_id}, trying alternatives")
                
                # Try other common indices
                alternative_indices = [1, 0, 2]
                for alt_id in alternative_indices:
                    if alt_id == device_id:  # Skip the one we already tried
                        continue
                        
                    self.logger.info(f"Trying camera with device_id={alt_id}")
                    if self.add_camera("main", alt_id, "Main Camera", True):
                        self.logger.info(f"Successfully connected to camera with device_id={alt_id}")
                        break
            
            # Check for video file to use as a second source for testing
            video_path = os.path.join("videos", "cam_test.mp4")
            if os.path.exists(video_path):
                self.logger.info(f"Found test video at {video_path}, adding as second camera")
                self.add_camera("secondary", video_path, "Secondary Camera", True)
        
        except Exception as e:
            self.logger.error(f"Error initializing default camera: {e}")
    
    def add_camera(self, camera_id, source, name=None, enabled=True):
        """
        Add a new camera to the registry
        
        Args:
            camera_id: Unique ID for the camera
            source: Camera source (device ID or RTSP URL)
            name: Human-readable name for the camera
            enabled: Whether the camera is enabled by default
            
        Returns:
            bool: True if added successfully, False otherwise
        """
        with self.lock:
            try:
                # Convert source to appropriate type if it's a numeric string
                if isinstance(source, str) and source.isdigit():
                    try:
                        source = int(source)
                        self.logger.info(f"Converted string source '{source}' to integer")
                    except ValueError:
                        # Keep as string if conversion fails
                        pass
                
                # Check if camera ID already exists and if we're already initialized
                is_replacement = camera_id in self.cameras
                if is_replacement and self.initialized:
                    old_camera = self.cameras[camera_id]
                    
                    # Only handle replacements during database loading if already initialized
                    # This prevents unnecessary camera open/close cycles
                    self.logger.info(f"Camera with ID {camera_id} already exists, comparing configurations")
                    
                    # If same source type, don't replace - just update name if needed
                    old_source = old_camera.device_id
                    if str(old_source) == str(source):
                        self.logger.info(f"Camera {camera_id} has same source {source}, keeping existing camera")
                        return True
                    
                    # Different source, need to stop old camera before replacement
                    self.logger.warning(f"Camera with ID {camera_id} has different source, replacing")
                    if old_camera.is_running:
                        old_camera.stop()
                        # Give time for proper shutdown
                        time.sleep(0.5)
                
                # Create a custom config for this camera
                camera_config = self.config.get('camera', {}).copy()
                camera_config['device_id'] = source
                camera_config['name'] = name or f"Camera {camera_id}"
                
                # Create a new resource provider with this camera-specific config
                camera_resource_provider = self.resource_provider.clone_with_custom_config({'camera': camera_config})
                
                # Create a new camera manager
                camera = CameraManager(camera_resource_provider)
                
                # Only test the connection if it's not a replacement and is a real device
                # We can skip this for the database loading phase to avoid USB reconnection issues
                if not is_replacement:
                    # Verify the camera can be opened before adding it
                    if not self._test_camera_connection(source):
                        self.logger.error(f"Failed to open camera source: {source}")
                        return False
                
                # Add to registry and start if enabled
                self.cameras[camera_id] = camera
                
                # Start the camera if enabled
                if enabled:
                    camera.start()
                    # Wait for camera to initialize
                    for _ in range(10):  # Up to 1 second wait
                        if hasattr(camera, 'is_initialized') and camera.is_initialized:
                            break
                        time.sleep(0.1)
                
                self.logger.info(f"Added camera {camera_id} ({name or 'unnamed'}) with source {source}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error adding camera {camera_id}: {e}")
                return False
    
    def _test_camera_connection(self, source):
        """
        Test if a camera can be successfully opened
        
        Args:
            source: Camera source (device ID or URL)
            
        Returns:
            bool: True if camera can be opened, False otherwise
        """
        try:
            # Check if it's a video file
            if isinstance(source, str) and (
                source.endswith('.mp4') or 
                source.endswith('.avi') or 
                source.endswith('.mov') or 
                source.endswith('.mkv')):
                # For video files, just check if the file exists
                if os.path.exists(source):
                    return True
                return False
                
            # For USB or IP cameras, test opening with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                self.logger.info(f"Attempting to open camera source {source} (attempt {attempt+1}/{max_retries})")
                
                # For Raspberry Pi, try both numeric and string path formats
                if isinstance(source, int):
                    sources_to_try = [source, f"/dev/video{source}"]
                else:
                    sources_to_try = [source]
                
                for src in sources_to_try:
                    cap = cv2.VideoCapture(src)
                    if cap.isOpened():
                        # Successfully opened, try to read a frame
                        ret, _ = cap.read()
                        cap.release()
                        
                        if ret:
                            self.logger.info(f"Successfully connected to camera source: {src}")
                            return True
                    
                    # Release capture object
                    cap.release()
                
                # If we get here, the attempt failed - wait before retrying
                if attempt < max_retries - 1:
                    self.logger.info(f"Waiting before retry for camera {source}")
                    time.sleep(1)  # Wait a second before retry
            
            self.logger.error(f"Failed to open camera source after {max_retries} attempts: {source}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error testing camera connection: {e}")
            return False
    
    def remove_camera(self, camera_id):
        """
        Remove a camera from the registry
        
        Args:
            camera_id: ID of the camera to remove
            
        Returns:
            bool: True if removed successfully, False otherwise
        """
        with self.lock:
            try:
                if camera_id not in self.cameras:
                    self.logger.warning(f"Camera with ID {camera_id} does not exist")
                    return False
                
                # Stop the camera
                camera = self.cameras[camera_id]
                if camera.is_running:
                    camera.stop()
                    # Give time for proper shutdown
                    time.sleep(0.5)
                
                # Remove from registry
                del self.cameras[camera_id]
                
                self.logger.info(f"Removed camera {camera_id}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error removing camera {camera_id}: {e}")
                return False
    
    def get_camera(self, camera_id):
        """
        Get a camera by ID
        
        Args:
            camera_id: ID of the camera to get
            
        Returns:
            CameraManager: The camera manager, or None if not found
        """
        with self.lock:
            return self.cameras.get(camera_id)
    
    def get_all_cameras(self):
        """
        Get all cameras in the registry
        
        Returns:
            dict: Dictionary of camera_id -> CameraManager
        """
        with self.lock:
            return self.cameras.copy()
    
    def get_active_cameras(self):
        """
        Get all active cameras in the registry
        
        Returns:
            dict: Dictionary of camera_id -> CameraManager for active cameras
        """
        with self.lock:
            return {
                camera_id: camera
                for camera_id, camera in self.cameras.items()
                if camera.is_running and (hasattr(camera, 'is_initialized') and camera.is_initialized)
            }
    
    def start_all_cameras(self):
        """
        Start all cameras in the registry
        """
        with self.lock:
            for camera_id, camera in self.cameras.items():
                if not camera.is_running:
                    camera.start()
                    self.logger.info(f"Started camera {camera_id}")
    
    def stop_all_cameras(self):
        """
        Stop all cameras in the registry
        """
        with self.lock:
            for camera_id, camera in self.cameras.items():
                if camera.is_running:
                    camera.stop()
                    self.logger.info(f"Stopped camera {camera_id}")
    
    def get_camera_count(self):
        """
        Get the number of cameras in the registry
        
        Returns:
            int: Number of cameras
        """
        with self.lock:
            return len(self.cameras) 