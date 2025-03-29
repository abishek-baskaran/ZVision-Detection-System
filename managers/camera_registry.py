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
    
    def __init__(self, resource_provider):
        """
        Initialize the camera registry
        
        Args:
            resource_provider: The resource provider for config and logging
        """
        self.logger = resource_provider.get_logger()
        self.config = resource_provider.get_config()
        self.resource_provider = resource_provider
        
        # Dictionary of camera_id -> CameraManager
        self.cameras = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Load default camera configuration
        self._init_default_camera()
        
        self.logger.info(f"CameraRegistry initialized with {len(self.cameras)} cameras")
    
    def _init_default_camera(self):
        """
        Initialize the default camera from config
        """
        try:
            # Get camera settings from config
            camera_config = self.config.get('camera', {})
            device_id = camera_config.get('device_id', 0)
            
            # Add the default camera
            self.add_camera("main", device_id, "Main Camera", True)
            
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
                # Check if camera ID already exists
                if camera_id in self.cameras:
                    self.logger.warning(f"Camera with ID {camera_id} already exists, replacing")
                    old_camera = self.cameras[camera_id]
                    if old_camera.is_running:
                        old_camera.stop()
                
                # Create a custom config for this camera
                camera_config = self.config.get('camera', {}).copy()
                camera_config['device_id'] = source
                camera_config['name'] = name or f"Camera {camera_id}"
                
                # Create a new resource provider with this camera-specific config
                camera_resource_provider = self.resource_provider.clone_with_custom_config({'camera': camera_config})
                
                # Create a new camera manager
                camera = CameraManager(camera_resource_provider)
                self.cameras[camera_id] = camera
                
                # Start the camera if enabled
                if enabled:
                    camera.start()
                
                self.logger.info(f"Added camera {camera_id} ({name or 'unnamed'}) with source {source}")
                return True
                
            except Exception as e:
                self.logger.error(f"Error adding camera {camera_id}: {e}")
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
                if camera.is_running
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