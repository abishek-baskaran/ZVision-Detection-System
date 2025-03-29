#!/usr/bin/env python3
# Test script for ROI and entry/exit functionality in DetectionManager
# Run this test with:
#   python -m unittest tests/unit/test_roi_detection.py
# or:
#   cd tests/unit && python test_roi_detection.py

import cv2
import numpy as np
import time
import unittest
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import sys
import threading

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import required modules
from managers.resource_provider import ResourceProvider
from managers.detection_manager import DetectionManager

class MockResourceProvider:
    """
    Mock resource provider
    """
    def __init__(self):
        self.config = {
            'detection': {
                'model_path': 'yolov8n.pt',
                'confidence_threshold': 0.25,
                'idle_fps': 1,
                'active_fps': 5,
                'person_class_id': 0,
                'direction_threshold': 20
            }
        }
        
    def get_logger(self):
        logger = MagicMock()
        return logger
        
    def get_config(self):
        return self.config

class MockCameraManager:
    """
    Mock camera manager that provides test frames
    """
    def __init__(self):
        # Create a black test image (640x480)
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        
    def set_person_position(self, x, y, width=100, height=200):
        """Set a person rectangle at the specified position"""
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(self.frame, (x, y), (x + width, y + height), (0, 255, 0), -1)
        
    def get_latest_frame(self):
        return self.frame

class MockDatabaseManager:
    """
    Mock database manager
    """
    def __init__(self):
        self.settings = {}
        self.events = []
        
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)
        
    def set_setting(self, key, value):
        self.settings[key] = value
        return True
        
    def log_detection_event(self, event_type, direction=None, confidence=None, details=None):
        self.events.append({
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'event_type': event_type,
            'direction': direction,
            'confidence': confidence,
            'details': details
        })
        return True

class MockDashboardManager:
    """
    Mock dashboard manager
    """
    def __init__(self):
        self.detections = 0
        self.directions = {}
        self.footfalls = {}
        
    def record_detection(self):
        self.detections += 1
        
    def record_direction(self, direction):
        if direction in self.directions:
            self.directions[direction] += 1
        else:
            self.directions[direction] = 1
            
    def record_footfall(self, event_type):
        if event_type in self.footfalls:
            self.footfalls[event_type] += 1
        else:
            self.footfalls[event_type] = 1

class TestROIDetection(unittest.TestCase):
    """
    Test case for ROI and entry/exit functionality
    """
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create mock components
        self.rp = MockResourceProvider()
        self.camera = MockCameraManager()
        self.db = MockDatabaseManager()
        self.dashboard = MockDashboardManager()
        
        # Create a patched YOLO model
        self.model_patch = patch('ultralytics.YOLO')
        self.mock_yolo = self.model_patch.start()
        
        # Configure the mock YOLO model
        self.mock_model = MagicMock()
        self.mock_yolo.return_value = self.mock_model
        
        # Create the detection manager
        self.detector = DetectionManager(self.rp, self.camera, self.dashboard, self.db)
        
        # Patch the _detection_loop method to avoid starting the thread
        self.detector._detection_loop = MagicMock()
        
    def tearDown(self):
        """Clean up after each test"""
        self.model_patch.stop()
        
    def _setup_model_results(self, x, y, width=100, height=200, found=True):
        """Setup mock model results to simulate a person detection"""
        # Create a person at the specified position
        if found:
            # Create box with person detection
            mock_box = MagicMock()
            mock_box.cls = [np.array([0])]  # Person class
            mock_box.xyxy = [np.array([x, y, x + width, y + height])]
            
            # Create results with the box
            mock_result = MagicMock()
            mock_result.boxes = [mock_box]
            
            # Set up model to return these results
            self.mock_model.return_value = [mock_result]
        else:
            # Create empty results (no person)
            mock_result = MagicMock()
            mock_result.boxes = []
            
            # Set up model to return these results
            self.mock_model.return_value = [mock_result]
    
    def test_roi_filtering(self):
        """Test that detections are filtered by ROI"""
        # Set ROI to middle of the frame
        roi = (200, 150, 400, 350)
        self.detector.set_roi(roi)
        
        # 1. Test person inside ROI
        self._setup_model_results(250, 200)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person should be detected
        self.assertTrue(self.detector.is_person_detected())
        
        # 2. Test person outside ROI
        self._setup_model_results(50, 50)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person should not be detected (still true from previous detection)
        self.assertTrue(self.detector.is_person_detected())
        
        # Simulate multiple frames with no person in ROI
        for _ in range(10):
            self._setup_model_results(0, 0, found=False)
            self.detector._process_frame(self.camera.get_latest_frame())
            
        # After multiple frames without a person, detection should be False
        self.assertFalse(self.detector.is_person_detected())
        
        # 3. Clear ROI and test detection in any part of the frame
        self.detector.clear_roi()
        self._setup_model_results(50, 50)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person should be detected
        self.assertTrue(self.detector.is_person_detected())
    
    def test_entry_exit_mapping(self):
        """Test that direction is correctly mapped to entry/exit events"""
        # Set ROI to include the entire frame for this test
        roi = (0, 0, 640, 480)
        self.detector.set_roi(roi)
        
        # Set entry direction as left-to-right
        self.detector.set_entry_direction(DetectionManager.ENTRY_DIRECTION_LTR)
        
        # 1. Simulate left-to-right movement (entry)
        # Start on the left
        self._setup_model_results(100, 200)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Move right
        for x in range(150, 500, 50):
            self._setup_model_results(x, 200)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person moves out of frame
        for _ in range(10):
            self._setup_model_results(0, 0, found=False)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Check entry was recorded
        self.assertEqual(self.dashboard.footfalls.get('entry', 0), 1)
        
        # 2. Simulate right-to-left movement (exit)
        # Start on the right
        self._setup_model_results(500, 200)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Move left
        for x in range(450, 100, -50):
            self._setup_model_results(x, 200)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person moves out of frame
        for _ in range(10):
            self._setup_model_results(0, 0, found=False)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Check exit was recorded
        self.assertEqual(self.dashboard.footfalls.get('exit', 0), 1)
        
        # 3. Change entry direction and verify the opposite mapping
        self.detector.set_entry_direction(DetectionManager.ENTRY_DIRECTION_RTL)
        
        # Simulate right-to-left movement (now entry)
        self._setup_model_results(500, 200)
        self.detector._process_frame(self.camera.get_latest_frame())
        
        # Move left
        for x in range(450, 100, -50):
            self._setup_model_results(x, 200)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Person moves out of frame
        for _ in range(10):
            self._setup_model_results(0, 0, found=False)
            self.detector._process_frame(self.camera.get_latest_frame())
        
        # Check entry was recorded
        self.assertEqual(self.dashboard.footfalls.get('entry', 0), 2)
    
    def test_persistence(self):
        """Test that ROI and entry direction settings are saved and loaded correctly"""
        # Set initial values
        roi = (100, 100, 300, 300)
        entry_direction = DetectionManager.ENTRY_DIRECTION_LTR
        
        # Set values in detector
        self.detector.set_roi(roi)
        self.detector.set_entry_direction(entry_direction)
        
        # Check they were saved to database
        self.assertEqual(json.loads(self.db.settings['roi_coords']), list(roi))
        self.assertEqual(self.db.settings['entry_direction'], entry_direction)
        
        # Create a new detector to test loading
        new_detector = DetectionManager(self.rp, self.camera, self.dashboard, self.db)
        
        # Check values were loaded
        self.assertEqual(new_detector.get_roi(), roi)
        self.assertEqual(new_detector.get_entry_direction(), entry_direction)
        
        # Test clearing ROI
        new_detector.clear_roi()
        self.assertIsNone(new_detector.get_roi())
        self.assertNotIn('roi_coords', self.db.settings)

if __name__ == '__main__':
    unittest.main() 