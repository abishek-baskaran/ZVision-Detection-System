#!/usr/bin/env python3
# main.py - Entry point for the person detection system

import time
import logging
import signal
import sys
import os
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.camera_registry import CameraRegistry
from managers.detection_manager import DetectionManager
from managers.dashboard_manager import DashboardManager
from managers.api_manager import APIManager
from managers.database_manager import DatabaseManager
from managers.storage_manager import start_snapshot_cleanup_thread

class ZVision:
    """
    Main ZVision detection system class.
    Initializes and manages all system components.
    """
    def __init__(self):
        # Initialize resource provider for configuration and logging
        self.resource_provider = ResourceProvider("config.yaml")
        self.config = self.resource_provider.get_config()
        self.logger = self.resource_provider.get_logger()
        
        self.logger.info("Initializing ZVision system")
        
        # Initialize database manager
        self.db_manager = DatabaseManager(self.resource_provider)
        
        # Check if there are cameras already in the database
        cameras = self.db_manager.list_cameras()
        has_cameras_in_db = bool(cameras)
        
        # Initialize camera registry - skip default init if we have cameras in DB
        self.logger.info("Initializing camera registry...")
        if has_cameras_in_db:
            self.logger.info(f"Found {len(cameras)} cameras in database, skipping default camera initialization")
        self.camera_registry = CameraRegistry(self.resource_provider, skip_default_init=has_cameras_in_db)
        
        # Load cameras from database if available
        if cameras:
            self.logger.info(f"Loading {len(cameras)} cameras from database")
            for cam in cameras:
                cam_id = cam["camera_id"]
                src = cam["source"]
                name = cam.get("name", f"Camera {cam_id}")
                width = cam.get("width")
                height = cam.get("height")
                fps = cam.get("fps")
                enabled = cam.get("enabled", 1)
                
                # Add the camera to the registry
                if self.camera_registry.add_camera(cam_id, src, name=name):
                    self.logger.info(f"Added camera {cam_id} from database configuration")
                    
                    # Start camera if it was enabled
                    if enabled:
                        camera = self.camera_registry.get_camera(cam_id)
                        if camera and not camera.is_running:
                            camera.start()
        else:
            # No cameras in database, initialize with default
            default_src = self.config.get('camera', {}).get('device_id', 0)
            self.camera_registry.add_camera("main", default_src, name="Camera main")
            self.db_manager.add_camera("main", default_src, "Camera main")
            
            # Also add a secondary demo camera if video file exists
            demo_video = "videos/cam_test.mp4"
            if os.path.exists(demo_video):
                self.camera_registry.add_camera("secondary", demo_video, name="Camera secondary")
                self.db_manager.add_camera("secondary", demo_video, "Camera secondary")
        
        self.logger.info(f"Camera registry initialized with {self.camera_registry.get_camera_count()} cameras")
        
        # Initialize camera manager and start capturing frames (for backward compatibility)
        self.logger.info("Starting camera manager...")
        self.camera_manager = self.camera_registry.get_camera("main")
        if not self.camera_manager:
            self.logger.warning("Main camera not found in registry, creating default camera manager")
            self.camera_manager = CameraManager(self.resource_provider)
            self.camera_manager.start()
        
        self.logger.info("Camera manager started successfully")
        
        # Initialize dashboard manager (not connected to detection manager yet)
        self.logger.info("Initializing dashboard manager...")
        self.dashboard_manager = DashboardManager(self.resource_provider)
        self.logger.info("Dashboard manager initialized")
        
        # Initialize detection manager and link it to camera registry, dashboard manager, and database manager
        self.logger.info("Initializing detection manager...")
        self.detection_manager = DetectionManager(
            self.resource_provider,
            self.camera_registry,
            self.dashboard_manager,
            self.db_manager
        )
        
        # Apply ROI settings for each camera from database
        for cam_id in self.camera_registry.get_all_cameras().keys():
            roi_cfg = self.db_manager.get_camera_roi(cam_id)
            if roi_cfg:
                self.logger.info(f"Applying ROI configuration for camera {cam_id}")
                coords = (
                    roi_cfg["coords"]["x1"],
                    roi_cfg["coords"]["y1"],
                    roi_cfg["coords"]["x2"],
                    roi_cfg["coords"]["y2"]
                )
                entry_dir = roi_cfg["entry_direction"]
                self.detection_manager.set_roi(cam_id, coords)
                self.detection_manager.set_entry_direction(cam_id, entry_dir)
        
        self.logger.info("Starting detection manager...")
        self.detection_manager.start_all()
        self.logger.info("Detection manager started successfully")
        
        # Now that detection_manager is initialized, update dashboard_manager reference
        self.dashboard_manager.detection_manager = self.detection_manager
        
        # Initialize API manager
        self.logger.info("Initializing API manager...")
        self.api_manager = APIManager(
            self.resource_provider, 
            self.camera_manager,  # Keep for backward compatibility
            self.detection_manager, 
            self.dashboard_manager,
            self.db_manager,
            self.camera_registry  # Pass camera registry to API manager
        )
        self.logger.info("API manager initialized")
        
        # Set up signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Initialize and start snapshot storage manager
        self.logger.info("Starting snapshot storage manager...")
        # Get snapshot settings from config or use defaults
        snapshot_config = self.config.get('snapshots', {})
        max_files = snapshot_config.get('max_files', 1000)
        cleanup_interval = snapshot_config.get('cleanup_interval', 3600)  # Default to hourly cleanup
        
        # Start the snapshot cleanup thread
        self.snapshot_thread = start_snapshot_cleanup_thread(
            max_files=max_files,
            interval=cleanup_interval,
            logger=self.logger
        )
        self.logger.info(f"Snapshot storage manager started (max files: {max_files}, interval: {cleanup_interval}s)")
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Signal {sig} received, shutting down")
        try:
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Error during shutdown signal handling: {e}")
        # Force exit after shutdown to ensure all threads terminate
        self.logger.info("Exiting application")
        sys.exit(0)
    
    def start(self):
        """Start the API server (this will block)"""
        try:
            self.logger.info("Starting API server")
            self.api_manager.start()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received, shutting down")
            self.shutdown()
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            self.shutdown()
            sys.exit(1)
    
    def shutdown(self):
        """Clean shutdown of all components"""
        self.logger.info("Shutting down ZVision system")
        
        # First stop all detections
        if hasattr(self.detection_manager, 'stop_all'):
            try:
                self.logger.info("Stopping detection manager...")
                self.detection_manager.stop_all()
                self.logger.info("Detection manager stopped")
            except Exception as e:
                self.logger.error(f"Error stopping detection manager: {e}")
        
        # Then stop all cameras
        if hasattr(self.camera_registry, 'stop_all_cameras'):
            try:
                self.logger.info("Stopping all cameras...")
                self.camera_registry.stop_all_cameras()
                self.logger.info("All cameras stopped")
            except Exception as e:
                self.logger.error(f"Error stopping cameras: {e}")
        elif hasattr(self.camera_manager, 'stop'):
            try:
                self.logger.info("Stopping camera manager...")
                self.camera_manager.stop()
                self.logger.info("Camera manager stopped")
            except Exception as e:
                self.logger.error(f"Error stopping camera manager: {e}")
        
        # Finally, close the database
        if hasattr(self.db_manager, 'close'):
            try:
                self.logger.info("Closing database connection...")
                self.db_manager.close()
                self.logger.info("Database connection closed")
            except Exception as e:
                self.logger.error(f"Error closing database: {e}")
                
        self.logger.info("System shutdown complete")

# Backward compatibility for direct execution
def main():
    app = ZVision()
    app.start()

if __name__ == "__main__":
    main() 