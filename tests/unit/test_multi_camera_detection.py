import sys
import os
import unittest
import threading
import time
import cv2
import numpy as np
from unittest.mock import MagicMock, patch, PropertyMock

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from managers.resource_provider import ResourceProvider
from managers.camera_registry import CameraRegistry
from managers.detection_manager import DetectionManager
from managers.dashboard_manager import DashboardManager
from managers.database_manager import DatabaseManager

class TestMultiCameraDetection(unittest.TestCase):
    """
    Test the multi-camera detection functionality
    """
    
    def setUp(self):
        """
        Set up the test
        """
        # Mock the resource provider
        self.resource_provider = MagicMock()
        self.resource_provider.get_logger.return_value = MagicMock()
        self.resource_provider.get_config.return_value = {
            'detection': {
                'model_path': 'models/yolov8n.pt',
                'confidence_threshold': 0.25,
                'idle_fps': 1,
                'active_fps': 5,
                'person_class_id': 0
            },
            'camera': {
                'device_id': 0,
                'width': 640,
                'height': 480,
                'fps': 30
            }
        }
        self.resource_provider.clone_with_custom_config = MagicMock(return_value=self.resource_provider)
        
        # Create test images with and without people
        self.test_image_with_person = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(self.test_image_with_person, (100, 100), (300, 400), (0, 0, 255), -1)  # Red rectangle representing a person
        
        self.test_image_without_person = np.zeros((480, 640, 3), dtype=np.uint8)
        
        # Mock the camera manager
        self.mock_camera1 = MagicMock()
        self.mock_camera1.is_running = True
        self.mock_camera1.get_latest_frame.return_value = self.test_image_with_person
        self.mock_camera1._stop_detection = False
        
        self.mock_camera2 = MagicMock()
        self.mock_camera2.is_running = True
        self.mock_camera2.get_latest_frame.return_value = self.test_image_without_person
        self.mock_camera2._stop_detection = False
        
        # Mock camera registry
        self.camera_registry = MagicMock()
        self.camera_registry.get_camera.side_effect = lambda cam_id: self.mock_camera1 if cam_id == "main" else self.mock_camera2
        self.camera_registry.get_active_cameras.return_value = {"main": self.mock_camera1, "secondary": self.mock_camera2}
        self.camera_registry.get_all_cameras.return_value = {"main": self.mock_camera1, "secondary": self.mock_camera2}
        
        # Mock dashboard manager
        self.dashboard_manager = MagicMock()
        
        # Mock database manager
        self.db_manager = MagicMock()
        
        # Create proper mock YOLO results that will be processed correctly
        self.mock_yolo = MagicMock()
        
        # Create a properly structured mock result for detecting a person
        mock_result = MagicMock()
        mock_box = MagicMock()
        mock_box.cls = [0]  # Person class ID (pretend it's a tensor that can be converted to int)
        mock_box.xyxy = [MagicMock()]  # Create a mock for the xyxy tensor
        mock_box.xyxy[0].cpu.return_value.numpy.return_value = np.array([100, 100, 300, 400])
        
        mock_boxes = MagicMock()
        mock_boxes.__iter__.return_value = [mock_box]  # Make boxes iterable
        mock_result.boxes = mock_boxes
        
        # Create detection manager with patched YOLO
        with patch('managers.detection_manager.YOLO', return_value=self.mock_yolo):
            self.detection_manager = DetectionManager(
                self.resource_provider,
                self.camera_registry,
                self.dashboard_manager,
                self.db_manager
            )
            
        # Set the model return value to simulate person detection
        self.mock_yolo.return_value = [mock_result]
        self.detection_manager.model = self.mock_yolo
        
        # Initialize state for tests
        self.detection_manager.states = {
            "main": {
                "person_detected": False,
                "last_detection_time": None,
                "current_direction": self.detection_manager.DIRECTION_UNKNOWN,
                "no_person_counter": 0
            }
        }
    
    def test_start_all_cameras(self):
        """
        Test starting detection on all cameras
        """
        # Setup mock
        self.detection_manager.start_camera = MagicMock()
        
        # Call the method
        self.detection_manager.start_all()
        
        # Check that start_camera was called for each camera
        self.assertEqual(self.detection_manager.start_camera.call_count, 2)
        
        # Check calls
        self.detection_manager.start_camera.assert_any_call("main")
        self.detection_manager.start_camera.assert_any_call("secondary")
    
    def test_start_stop_specific_camera(self):
        """
        Test starting and stopping detection on a specific camera
        """
        # Set up the detection thread mock
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        
        # Patch threading.Thread to return our mock
        with patch('threading.Thread', return_value=mock_thread):
            # Start detection for the main camera
            self.detection_manager.start_camera("main")
            
            # Check that thread was created and started
            self.assertIn("main", self.detection_manager.detection_threads)
            mock_thread.start.assert_called_once()
            
            # Stop detection for the main camera
            self.detection_manager.stop_camera("main")
            
            # Check that the thread was joined and the camera flag was set properly
            mock_thread.join.assert_called_once()
            self.assertTrue(hasattr(self.mock_camera1, '_stop_detection'))
            
            # Check that the detection thread was removed from the dictionary
            self.assertNotIn("main", self.detection_manager.detection_threads)
    
    def test_process_frame_with_roi(self):
        """
        Test processing a frame with ROI
        """
        # Set up ROI for the camera
        self.detection_manager.roi_settings = {
            "main": {
                "coords": (50, 50, 400, 450),  # This includes the person
                "entry_direction": "LTR"
            }
        }
        
        # Create a direct implementation of _update_detection_state to capture args
        detected_person = [False]
        
        def capture_detection_state(camera_id, person_present, center_x):
            detected_person[0] = person_present
        
        # Mock the update method to capture detection
        self.detection_manager._update_detection_state = MagicMock(side_effect=capture_detection_state)
        
        # Process a frame
        self.detection_manager._process_frame(self.test_image_with_person, "main")
        
        # Check that the detection was properly processed
        self.detection_manager._update_detection_state.assert_called_once()
        self.assertTrue(detected_person[0], "Person should have been detected in the frame")
        
    def test_resource_monitoring(self):
        """
        Test resource monitoring functionality
        """
        # Call the resource check method
        self.detection_manager._check_system_resources()
        
        # Check that CPU and memory usage histories were updated
        self.assertEqual(len(self.detection_manager.cpu_usage_history), 1)
        self.assertEqual(len(self.detection_manager.memory_usage_history), 1)
        
        # Get the resource info
        resources = self.detection_manager.get_system_resources()
        
        # Check that the resources were returned correctly
        self.assertIn('cpu_percent', resources)
        self.assertIn('memory_percent', resources)
        self.assertIn('avg_cpu', resources)
        self.assertIn('avg_memory', resources)

if __name__ == '__main__':
    unittest.main() 