#!/usr/bin/env python3
# main.py - Entry point for the person detection system

import time
import logging
import signal
import sys
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.detection_manager import DetectionManager
from managers.dashboard_manager import DashboardManager
from managers.api_manager import APIManager
from managers.database_manager import DatabaseManager

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
        
        # Initialize camera manager and start capturing frames
        self.logger.info("Starting camera manager...")
        self.camera_manager = CameraManager(self.resource_provider)
        self.camera_manager.start()
        self.logger.info("Camera manager started successfully")
        
        # Initialize dashboard manager (not connected to detection manager yet)
        self.logger.info("Initializing dashboard manager...")
        self.dashboard_manager = DashboardManager(self.resource_provider)
        self.logger.info("Dashboard manager initialized")
        
        # Initialize detection manager and link it to camera manager, dashboard manager, and database manager
        self.logger.info("Initializing detection manager...")
        self.detection_manager = DetectionManager(
            self.resource_provider,
            self.camera_manager,
            self.dashboard_manager,
            self.db_manager
        )
        self.logger.info("Starting detection manager...")
        self.detection_manager.start()
        self.logger.info("Detection manager started successfully")
        
        # Now that detection_manager is initialized, update dashboard_manager reference
        self.dashboard_manager.detection_manager = self.detection_manager
        
        # Initialize API manager
        self.logger.info("Initializing API manager...")
        self.api_manager = APIManager(
            self.resource_provider, 
            self.camera_manager, 
            self.detection_manager, 
            self.dashboard_manager,
            self.db_manager
        )
        self.logger.info("API manager initialized")
        
        # Set up signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Signal {sig} received, shutting down")
        self.shutdown()
        sys.exit(0)
    
    def start(self):
        """Start the API server (this will block)"""
        try:
            self.logger.info("Starting API server")
            self.api_manager.start()
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received, shutting down")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
            self.shutdown()
    
    def shutdown(self):
        """Clean shutdown of all components"""
        self.logger.info("Shutting down ZVision system")
        
        try:
            if hasattr(self.detection_manager, 'stop'):
                self.detection_manager.stop()
            
            if hasattr(self.camera_manager, 'stop'):
                self.camera_manager.stop()
            
            if hasattr(self.db_manager, 'close'):
                self.db_manager.close()
                
            self.logger.info("System shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

# Backward compatibility for direct execution
def main():
    app = ZVision()
    app.start()

if __name__ == "__main__":
    main() 