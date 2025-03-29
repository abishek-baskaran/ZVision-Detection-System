#!/usr/bin/env python3
# Manual Integration Test for ROI and Entry/Exit Functionality
# Run this test with:
#   python tests/manual/test_roi_integration.py
# 
# This test provides an interactive menu to test:
# - Setting and clearing ROI
# - Configuring entry/exit direction mapping
# - Viewing detection stats and entry/exit counts
# - Uses the actual camera feed for real-world testing

import sys
import os
import time
import cv2
import numpy as np
import threading

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import components
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.dashboard_manager import DashboardManager
from managers.database_manager import DatabaseManager
from managers.detection_manager import DetectionManager

def print_menu():
    """Print the test menu"""
    print("\n--- ROI Integration Test Menu ---")
    print("1. Set ROI to doorway area (300, 100, 400, 400)")
    print("2. Clear ROI")
    print("3. Set entry direction to Left-to-Right")
    print("4. Set entry direction to Right-to-Left")
    print("5. View current stats")
    print("q. Quit")
    print("-----------------------------")

def main():
    """Main integration test function"""
    print("Integration test for ROI and Entry/Exit functionality")
    print("====================================================")
    print("This test uses the real camera feed to test ROI functionality and entry/exit classification.")
    print("It allows you to configure the ROI and direction settings, then watch as the system")
    print("tracks people entering and exiting the configured region.")
    
    # Initialize resource provider with config
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.yaml")
    rp = ResourceProvider(config_path)
    
    # Create real components
    db_manager = DatabaseManager(rp)
    camera = CameraManager(rp)
    
    # First create detection manager since the dashboard needs it
    detector = DetectionManager(rp, camera, None, db_manager)
    
    # Create dashboard manager with the detection manager for monitoring
    dashboard = DashboardManager(rp, detector)
    
    # Connect dashboard to detection manager
    detector.dashboard_manager = dashboard
    
    # Start components
    camera.start()
    detector.start()
    
    print("\nComponents started successfully.")
    print("Configure the ROI around the area where you want to detect people (like a doorway).")
    print("Then configure which direction is considered an 'entry'.")
    print("The system will automatically track and categorize movements through the ROI.")
    
    try:
        running = True
        while running:
            print_menu()
            choice = input("Enter your choice: ")
            
            if choice == '1':
                # Set ROI to doorway area - using reasonable default values
                # These can be adjusted based on your camera and environment
                detector.set_roi((300, 100, 400, 400))
                print("ROI set to doorway area: (300, 100, 400, 400)")
                print("Note: Adjust these values if needed for your specific camera setup")
                
            elif choice == '2':
                # Clear ROI
                detector.clear_roi()
                print("ROI cleared - detection now uses the full frame")
                
            elif choice == '3':
                # Set entry direction to LTR
                detector.set_entry_direction(DetectionManager.ENTRY_DIRECTION_LTR)
                print("Entry direction set to Left-to-Right")
                print("People moving left to right will be counted as entries")
                print("People moving right to left will be counted as exits")
                
            elif choice == '4':
                # Set entry direction to RTL
                detector.set_entry_direction(DetectionManager.ENTRY_DIRECTION_RTL)
                print("Entry direction set to Right-to-Left")
                print("People moving right to left will be counted as entries")
                print("People moving left to right will be counted as exits")
                
            elif choice == '5':
                # View current stats
                roi = detector.get_roi()
                entry_dir = detector.get_entry_direction()
                
                print("\nCurrent Configuration:")
                print(f"ROI: {roi}")
                print(f"Entry Direction: {entry_dir}")
                
                print("\nDetection Stats:")
                stats = dashboard.get_summary()
                print(f"Total Detections: {stats.get('detection_count', 0)}")
                print(f"Direction Counts: {stats.get('direction_counts', {})}")
                print(f"Footfall Counts: {stats.get('footfall_counts', {})}")
                
                # Show latest events
                print("\nLatest Events:")
                recent_events = dashboard.get_recent_detections(5)
                for event in recent_events:
                    print(f"- {event}")
                
            elif choice.lower() == 'q':
                running = False
                print("Quitting test...")
            
            else:
                print("Invalid choice. Please try again.")
            
            # Give time for user to read the output
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nTest interrupted.")
    finally:
        # Stop all components
        detector.stop()
        camera.stop()
        print("Test completed and components stopped.")

if __name__ == "__main__":
    main() 