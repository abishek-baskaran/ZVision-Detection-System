#!/usr/bin/env python3
# Test script for DetectionManager

import cv2
import numpy as np
import time
import threading
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.dashboard_manager import DashboardManager
from managers.database_manager import DatabaseManager
from managers.detection_manager import DetectionManager

class MockCameraManager:
    """
    Mock camera manager that provides test images
    """
    def __init__(self, test_image_path):
        self.test_image = cv2.imread(test_image_path)
        if self.test_image is None:
            # Create a black test image with a white rectangle as fallback
            self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.rectangle(self.test_image, (100, 100), (300, 300), (255, 255, 255), -1)
        
        # Create a moving test sequence
        self.test_sequence = []
        for i in range(30):
            img = self.test_image.copy()
            # Draw a "person" moving from left to right
            offset = i * 20
            cv2.rectangle(img, (offset, 200), (offset + 100, 350), (0, 255, 0), -1)
            self.test_sequence.append(img)

    def get_latest_frame(self):
        # Return the current frame from sequence based on time
        return self.test_sequence[int(time.time() * 2) % len(self.test_sequence)]

    def start(self):
        pass

    def stop(self):
        pass

def main():
    # Initialize ResourceProvider
    rp = ResourceProvider("config.yaml")
    
    # Get a logger for this test
    logger = rp.get_logger("TestDetectionManager")
    logger.info("Starting DetectionManager test")
    
    # Check if we should use real camera or mock
    use_real_camera = False
    
    if use_real_camera:
        # Initialize real components
        camera = CameraManager(rp)
        dashboard = DashboardManager(rp)
        db = DatabaseManager(rp)
    else:
        # Use mock camera for testing
        logger.info("Using mock camera with test images")
        camera = MockCameraManager("test_person.jpg")
        dashboard = DashboardManager(rp)
        db = DatabaseManager(rp)
    
    # Initialize and start CameraManager if real
    if use_real_camera:
        camera.start()
    
    # Initialize DetectionManager
    detector = DetectionManager(rp, camera, dashboard, db)
    
    # Start detection
    detector.start()
    
    # Run test for 30 seconds
    logger.info("Detection started, running for 30 seconds...")
    
    try:
        # Monitor detection status
        for i in range(30):
            status = detector.get_detection_status()
            logger.info(f"Detection status: {status}")
            time.sleep(1)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        # Stop detection and camera
        detector.stop()
        if use_real_camera:
            camera.stop()
    
    logger.info("DetectionManager test completed")

if __name__ == "__main__":
    main() 