#!/usr/bin/env python3
# Test script for APIManager

import threading
import time
import json
import numpy as np
import cv2
from managers.resource_provider import ResourceProvider
from managers.api_manager import APIManager

# Mock classes for testing
class MockCameraManager:
    def __init__(self):
        # Create a test image
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(self.frame, "Test Camera Feed", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    def get_latest_frame(self):
        return self.frame
    
    def start(self):
        pass
    
    def stop(self):
        pass

class MockDetectionManager:
    def __init__(self):
        self.person_detected = False
    
    def get_detection_status(self):
        return {
            "person_detected": self.person_detected,
            "last_detection_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": "unknown"
        }
    
    def start(self):
        pass
    
    def stop(self):
        pass

class MockDashboardManager:
    def __init__(self):
        pass
    
    def get_summary(self):
        return {
            "total_detections": 42,
            "direction_counts": {
                "left_to_right": 25,
                "right_to_left": 15,
                "unknown": 2
            },
            "last_detection_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_direction": "left_to_right"
        }
    
    def get_total_metrics(self):
        return {
            "detection_count": 42,
            "direction_counts": {
                "left_to_right": 25,
                "right_to_left": 15,
                "unknown": 2
            }
        }
    
    def get_hourly_metrics(self, hours=24):
        current_hour = time.strftime("%Y-%m-%d %H:00")
        return {
            current_hour: {
                "detection_count": 42,
                "left_to_right": 25,
                "right_to_left": 15,
                "unknown": 2
            }
        }

class MockDatabaseManager:
    def __init__(self):
        pass
    
    def get_events(self, limit=50):
        events = []
        for i in range(min(5, limit)):
            events.append({
                "id": i + 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "type": "test_event",
                "data": json.dumps({"test": True, "value": i})
            })
        return events
    
    def get_recent_detection_events(self, limit=10):
        events = []
        for i in range(min(5, limit)):
            events.append({
                "id": i + 1,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event_type": "detection",
                "direction": "left_to_right" if i % 2 == 0 else "right_to_left",
                "details": json.dumps({"confidence": 0.95, "position": [100, 200]})
            })
        return events

def main():
    # Initialize ResourceProvider
    rp = ResourceProvider("config.yaml")
    
    # Get a logger for this test
    logger = rp.get_logger("TestAPIManager")
    logger.info("Starting APIManager test")
    
    # Create mock components
    camera = MockCameraManager()
    detection = MockDetectionManager()
    dashboard = MockDashboardManager()
    db = MockDatabaseManager()
    
    # Initialize APIManager
    api = APIManager(rp, camera, detection, dashboard, db)
    
    # Start API in a separate thread
    api_thread = threading.Thread(target=api.start)
    api_thread.daemon = True
    api_thread.start()
    
    # Print instructions for testing
    logger.info("API server started")
    logger.info("Test URLs:")
    logger.info("  - Main test page: http://localhost:5000/")
    logger.info("  - Status API: http://localhost:5000/api/status")
    logger.info("  - Events API: http://localhost:5000/api/events")
    logger.info("  - Metrics API: http://localhost:5000/api/metrics")
    logger.info("  - Frame API: http://localhost:5000/api/frame/current")
    logger.info("Press Ctrl+C to stop")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
            
            # Toggle person detected every 5 seconds for testing
            if int(time.time()) % 10 < 5:
                detection.person_detected = True
            else:
                detection.person_detected = False
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    
    logger.info("APIManager test completed")

if __name__ == "__main__":
    main() 