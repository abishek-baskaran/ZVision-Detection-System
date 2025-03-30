#!/usr/bin/env python3
# Test script for Snapshot Capture functionality

import unittest
import os
import time
import shutil
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch
import cv2
import numpy as np

# Import required modules
from managers.resource_provider import ResourceProvider
from managers.database_manager import DatabaseManager
from managers.detection_manager import DetectionManager

class TestSnapshotCapture(unittest.TestCase):
    """Test case for snapshot capture functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a temporary directory for snapshots
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = os.path.join(self.temp_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        # Create a test frame
        self.test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(self.test_frame, (100, 100), (300, 300), (255, 255, 255), -1)
        
        # Create test database
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
        # Mock the resource provider
        self.mock_rp = MagicMock()
        self.mock_rp.get_logger.return_value = MagicMock()
        self.mock_rp.get_config.return_value = {
            'detection': {
                'model_path': 'yolov8n.pt',
                'confidence_threshold': 0.25
            },
            'snapshots': {
                'max_files': 20,
                'cleanup_interval': 60
            },
            'database': {
                'path': self.db_path
            }
        }
        
        # Mock camera registry
        self.mock_camera_registry = MagicMock()
        self.mock_camera = MagicMock()
        self.mock_camera.get_latest_frame.return_value = self.test_frame
        self.mock_camera.is_running = True
        self.mock_camera_registry.get_camera.return_value = self.mock_camera
        self.mock_camera_registry.get_active_cameras.return_value = {'main': self.mock_camera}
        
        # Initialize real database manager with mock resource provider
        self.db_manager = DatabaseManager(self.mock_rp)
        
        # Patch os.path.exists to return True for snapshot path checks
        self.exists_patch = patch('os.path.exists', return_value=True)
        self.exists_patch.start()
        
        # Create detection manager with mocks
        self.detection_manager = DetectionManager(
            self.mock_rp, 
            self.mock_camera_registry, 
            dashboard_manager=MagicMock(),
            db_manager=self.db_manager
        )
        
        # Patch the model and detection processing
        self.detection_manager.model = MagicMock()
        
    def tearDown(self):
        """Clean up after each test"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Stop the path patch
        self.exists_patch.stop()
    
    @patch('cv2.imwrite')
    def test_snapshot_saved_on_detection(self, mock_imwrite):
        """Test that snapshots are saved when a person is detected"""
        # Set up mock to simulate a person being detected
        def save_snapshot_side_effect(camera_id, frame):
            # Return a mock filename
            filename = f"snapshots/camera_{camera_id}_timestamp.jpg"
            return filename
        
        # Replace the _save_snapshot method to avoid actual file writes
        with patch.object(
            self.detection_manager, 
            '_save_snapshot', 
            side_effect=save_snapshot_side_effect
        ):
            # Call update detection state with person_present=True
            self.detection_manager._update_detection_state('main', True, self.test_frame, 320)
            
            # Verify _save_snapshot was called
            self.detection_manager._save_snapshot.assert_called_once()
            
            # Verify detection was logged in database
            latest_events = self.db_manager.get_recent_detection_events(limit=1)
            self.assertTrue(len(latest_events) > 0)
            latest_event = latest_events[0]
            
            # Check event was logged with snapshot_path
            self.assertEqual(latest_event['event_type'], 'detection_start')
            self.assertEqual(latest_event['camera_id'], 'main')
            self.assertTrue('snapshot_path' in latest_event)
            self.assertIsNotNone(latest_event['snapshot_path'])
    
    @patch('cv2.imwrite')
    def test_snapshot_saved_on_person_disappear(self, mock_imwrite):
        """Test that snapshots are saved when a person disappears"""
        # Set up mock to simulate a person being detected and then disappearing
        def save_snapshot_side_effect(camera_id, frame):
            # Return a mock filename
            filename = f"snapshots/camera_{camera_id}_timestamp.jpg"
            return filename
        
        # Replace the _save_snapshot method to avoid actual file writes
        with patch.object(
            self.detection_manager, 
            '_save_snapshot', 
            side_effect=save_snapshot_side_effect
        ):
            # First trigger a detection
            self.detection_manager._update_detection_state('main', True, self.test_frame, 320)
            self.detection_manager._save_snapshot.reset_mock()
            
            # Now simulate person disappearing
            # We need to set no_person_counter to 5 to trigger the "person gone" logic
            camera_state = self.detection_manager.states['main']
            camera_state['person_detected'] = True
            camera_state['no_person_counter'] = 5
            
            # Update state with person_present=False
            self.detection_manager._update_detection_state('main', False, self.test_frame, None)
            
            # Verify _save_snapshot was called again
            self.detection_manager._save_snapshot.assert_called_once()
            
            # Manually retrieve detection events and check for the latest "detection_end" event
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM detection_events WHERE event_type = 'detection_end' ORDER BY timestamp DESC LIMIT 1"
            )
            end_event = cursor.fetchone()
            conn.close()
            
            # Check that a detection_end event was logged
            self.assertIsNotNone(end_event, "No detection_end event was logged")
            if end_event:
                # Convert to dictionary for easier access
                end_event_dict = dict(end_event)
                
                self.assertEqual(end_event_dict['event_type'], 'detection_end')
                self.assertEqual(end_event_dict['camera_id'], 'main')
                self.assertTrue('snapshot_path' in end_event_dict)
                self.assertIsNotNone(end_event_dict['snapshot_path'])
    
    def test_snapshot_naming_convention(self):
        """Test that snapshots follow the correct naming convention"""
        # Call the actual _save_snapshot method
        with patch('cv2.imwrite', return_value=True):
            snapshot_path = self.detection_manager._save_snapshot('test', self.test_frame)
            
            # Verify the path format is correct
            self.assertTrue('snapshots/camera_test_' in snapshot_path)
            self.assertTrue(snapshot_path.endswith('.jpg'))
            
            # Verify the timestamp format in the filename
            filename = os.path.basename(snapshot_path)
            parts = filename.split('_')
            
            # Format should be camera_[camera_id]_[timestamp].jpg
            self.assertEqual(parts[0], 'camera')
            self.assertEqual(parts[1], 'test')
            
            # The timestamp should be parseable (YYYYMMDD_HHMMSS_microseconds)
            timestamp_parts = '_'.join(parts[2:]).replace('.jpg', '')
            self.assertTrue(len(timestamp_parts) >= 15)  # At least YYYYMMDD_HHMMSS
            
if __name__ == "__main__":
    unittest.main() 