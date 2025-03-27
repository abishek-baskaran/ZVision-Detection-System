#!/usr/bin/env python3
# Test script for CameraManager

from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
import cv2
import time
import sys

def main():
    # Initialize ResourceProvider
    rp = ResourceProvider("config.yaml")
    
    # Get a logger for this test
    logger = rp.get_logger("TestCameraManager")
    logger.info("Starting CameraManager test")
    
    # Initialize and start CameraManager
    cam = CameraManager(rp)
    cam.start()
    
    logger.info("Camera started, waiting for frames...")
    time.sleep(2)  # Allow camera time to initialize
    
    # Test capturing frames
    frame_count = 0
    start_time = time.time()
    test_duration = 5  # Run test for 5 seconds
    
    try:
        while time.time() - start_time < test_duration:
            # Get frame with timeout
            frame = cam.get_frame(block=True, timeout=1.0)
            
            if frame is not None:
                frame_count += 1
                
                # Save the first frame as a sample
                if frame_count == 1:
                    logger.info("Saving sample frame to sample_frame.jpg")
                    cv2.imwrite("sample_frame.jpg", frame)
            
            logger.info(f"Captured frames: {frame_count}")
            time.sleep(0.1)  # Small delay
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    finally:
        # Stop the camera
        cam.stop()
    
    # Calculate FPS
    elapsed_time = time.time() - start_time
    fps = frame_count / elapsed_time if elapsed_time > 0 else 0
    
    logger.info(f"Test completed: Captured {frame_count} frames in {elapsed_time:.2f} seconds ({fps:.2f} FPS)")
    logger.info("CameraManager test completed")

if __name__ == "__main__":
    main() 