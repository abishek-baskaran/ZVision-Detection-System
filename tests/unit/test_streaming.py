#!/usr/bin/env python3
# Test script for MJPEG streaming

import time
import sys
import webbrowser
import socket
import threading
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.api_manager import APIManager

class MockManager:
    """Simple mock class for the managers we don't need to test streaming"""
    def __init__(self):
        pass
    
    def get_detection_status(self):
        return {"person_detected": False, "direction": "unknown", "last_detection_time": None}
    
    def get_summary(self):
        return {"total_detections": 0, "direction_counts": {"left_to_right": 0, "right_to_left": 0, "unknown": 0}}
    
    def get_events(self, limit=10):
        return []
    
    def get_total_metrics(self):
        return {"detection_count": 0}
    
    def get_hourly_metrics(self, hours=24):
        return {}
    
    def get_recent_detection_events(self, limit=10):
        return []

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "localhost"

def main():
    print("Starting MJPEG streaming test...")
    
    # Initialize ResourceProvider
    resource_provider = ResourceProvider("config.yaml")
    logger = resource_provider.get_logger()
    
    # Initialize CameraManager and start it
    camera_manager = CameraManager(resource_provider)
    camera_manager.start()
    
    # Create mock managers for other components
    mock_manager = MockManager()
    
    # Initialize APIManager 
    api_manager = APIManager(
        resource_provider, 
        camera_manager, 
        mock_manager,  # detection_manager
        mock_manager,  # dashboard_manager
        mock_manager   # db_manager
    )
    
    # Get local IP for accessing the stream
    local_ip = get_local_ip()
    port = resource_provider.get_config().get('api', {}).get('port', 5000)
    
    # Print instructions
    print("\nMJPEG Streaming Test")
    print("-----------------")
    print(f"Stream URL: http://{local_ip}:{port}/video_feed")
    print(f"Test page: http://{local_ip}:{port}/")
    print("Press Ctrl+C to exit")
    
    # Open browser to test page after a short delay
    def open_browser():
        time.sleep(1)
        webbrowser.open(f"http://{local_ip}:{port}/")
    
    threading.Thread(target=open_browser).start()
    
    # Start the API server
    try:
        api_manager.start()
    except KeyboardInterrupt:
        print("Test interrupted, shutting down...")
    finally:
        # Clean up resources
        camera_manager.stop()
        print("Test completed")

if __name__ == "__main__":
    main() 