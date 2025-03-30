#!/usr/bin/env python3
# Integration test for snapshot functionality

import unittest
import os
import time
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import cv2
import numpy as np
import sqlite3
import threading

# Import required modules
from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.detection_manager import DetectionManager
from managers.database_manager import DatabaseManager
from managers.storage_manager import SnapshotStorageManager, start_snapshot_cleanup_thread

class MockCamera:
    """Mock camera for integration testing"""
    def __init__(self, camera_id, test_frames):
        self.camera_id = camera_id
        self.test_frames = test_frames
        self.current_frame_idx = 0
        self.is_running = True
        self.name = f"Camera {camera_id}"
        self.device_id = f"test_{camera_id}"
        
    def get_latest_frame(self):
        """Return current test frame"""
        if not self.is_running or self.current_frame_idx >= len(self.test_frames):
            return None
        
        frame = self.test_frames[self.current_frame_idx]
        self.current_frame_idx = (self.current_frame_idx + 1) % len(self.test_frames)
        return frame
    
    def start(self):
        """Start the mock camera"""
        self.is_running = True
        
    def stop(self):
        """Stop the mock camera"""
        self.is_running = False

class MockCameraRegistry:
    """Mock camera registry for integration testing"""
    def __init__(self, cameras):
        self.cameras = cameras
        
    def get_camera(self, camera_id):
        """Get a camera by ID"""
        return self.cameras.get(camera_id)
    
    def get_active_cameras(self):
        """Get all active cameras"""
        return {k: v for k, v in self.cameras.items() if v.is_running}
    
    def get_all_cameras(self):
        """Get all cameras"""
        return self.cameras

class TestIntegrationSnapshot(unittest.TestCase):
    """Integration test for snapshot functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.snapshot_dir = os.path.join(self.temp_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        # Create test frames with and without a person
        self.frame_without_person = np.zeros((480, 640, 3), dtype=np.uint8)
        self.frame_with_person = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(self.frame_with_person, (100, 100), (300, 300), (255, 255, 255), -1)
        
        # Create test frames sequence for left-to-right movement
        self.test_frames = []
        for i in range(10):
            # First 3 frames without person
            if i < 3:
                self.test_frames.append(self.frame_without_person.copy())
            # Next 4 frames with person moving left to right
            elif i < 7:
                frame = self.frame_without_person.copy()
                offset = (i - 3) * 100
                cv2.rectangle(frame, (offset, 200), (offset + 100, 350), (0, 255, 0), -1)
                self.test_frames.append(frame)
            # Last 3 frames without person
            else:
                self.test_frames.append(self.frame_without_person.copy())
        
        # Create mock cameras
        self.cameras = {
            'main': MockCamera('main', self.test_frames),
            'secondary': MockCamera('secondary', self.test_frames)
        }
        
        # Create mock camera registry
        self.camera_registry = MockCameraRegistry(self.cameras)
        
        # Mock the resource provider
        self.mock_rp = MagicMock()
        self.mock_rp.get_logger.return_value = MagicMock()
        self.mock_rp.get_config.return_value = {
            'detection': {
                'model_path': 'yolov8n.pt',
                'confidence_threshold': 0.25
            },
            'database': {
                'path': self.db_path
            },
            'snapshots': {
                'max_files': 5,  # Very small value to test FIFO cleanup quickly
                'cleanup_interval': 1  # 1 second to test quickly
            }
        }
        
        # Initialize database manager with test database
        self.db_manager = DatabaseManager(self.mock_rp)
        
        # Create detection manager with mocks and real DB
        self.detection_manager = DetectionManager(
            self.mock_rp,
            self.camera_registry,
            dashboard_manager=MagicMock(),
            db_manager=self.db_manager
        )
        
        # Patch the _process_frame method to directly control detection
        self.process_frame_patch = patch.object(
            self.detection_manager, 
            '_process_frame',
            side_effect=self._mock_process_frame
        )
        self.process_frame_patch.start()
        
        # Patch the model loading
        self.model_patch = patch.object(
            self.detection_manager, 
            '_load_model',
            return_value=None
        )
        self.model_patch.start()
        self.detection_manager.model = MagicMock()
        
        # Initialize storage manager
        self.storage_manager = SnapshotStorageManager(
            directory=self.snapshot_dir,
            max_files=5,
            logger=self.mock_rp.get_logger()
        )
    
    def tearDown(self):
        """Clean up after each test"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Stop the patches
        self.process_frame_patch.stop()
        self.model_patch.stop()
    
    def _mock_process_frame(self, frame, camera_id):
        """Mock frame processing to simulate person detection"""
        # Check if the frame shows a "person" (has some white or green pixels)
        has_person = np.mean(frame) > 1.0
        
        # Determine center position (for testing direction)
        center_x = 320
        if has_person:
            # Find contours and get center of the largest one
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                c = max(contours, key=cv2.contourArea)
                M = cv2.moments(c)
                if M["m00"] > 0:
                    center_x = int(M["m10"] / M["m00"])
        
        # Use the detection manager's update method
        self.detection_manager._update_detection_state(camera_id, has_person, frame, center_x if has_person else None)
    
    def _verify_snapshots_taken(self, expected_count=None):
        """Verify that snapshots were taken and saved to disk"""
        # Get all snapshots
        snapshots = [f for f in os.listdir(self.snapshot_dir) if f.endswith('.jpg')]
        
        # Check count if expected is given
        if expected_count is not None:
            self.assertEqual(len(snapshots), expected_count, f"Expected {expected_count} snapshots, found {len(snapshots)}")
        
        # Check if snapshots exist
        self.assertTrue(len(snapshots) > 0, "No snapshots were taken")
        
        # Check file sizes to make sure they're valid images
        for snapshot in snapshots:
            path = os.path.join(self.snapshot_dir, snapshot)
            size = os.path.getsize(path)
            self.assertTrue(size > 100, f"Snapshot {snapshot} appears too small ({size} bytes)")
    
    def _verify_database_entries(self, expected_count=None):
        """Verify that database entries were created for snapshots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get detection events with snapshot paths
        cursor.execute("""
            SELECT id, event_type, camera_id, snapshot_path
            FROM detection_events
            WHERE snapshot_path IS NOT NULL
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Check count if expected is given
        if expected_count is not None:
            self.assertEqual(len(rows), expected_count, f"Expected {expected_count} database entries, found {len(rows)}")
        
        # Check if database entries exist
        self.assertTrue(len(rows) > 0, "No database entries with snapshot_path were created")
        
        # Check paths
        for row in rows:
            _, event_type, camera_id, path = row
            self.assertTrue(path.startswith('snapshots/camera_'), "Invalid snapshot path format")
            self.assertTrue(camera_id in path, f"Camera ID ({camera_id}) not in path ({path})")
    
    def test_complete_snapshot_workflow(self):
        """Test the complete snapshot workflow - capture, database logging, and FIFO cleanup"""
        # Start cleanup thread
        cleanup_thread = start_snapshot_cleanup_thread(
            directory=self.snapshot_dir,
            max_files=5,  # Very small to test FIFO quickly
            interval=1,   # 1 second to test quickly
            logger=self.mock_rp.get_logger()
        )
        
        # Start detection for main camera
        self.detection_manager.start_camera('main')
        
        # Wait for detection to process frames
        time.sleep(3)
        
        # Stop detection
        self.detection_manager.stop_camera('main')
        
        # At this point the camera should have gone through the entire test sequence:
        # - First without person, then with person (detection_start + snapshot)
        # - Then person disappearing (detection_end + snapshot)
        
        # Verify snapshots were taken (for both entry and exit)
        self._verify_snapshots_taken(expected_count=2)
        
        # Verify database entries were created
        self._verify_database_entries(expected_count=2)
        
        # Test FIFO cleanup by creating more snapshots
        # Repeat the test several times to generate more than max_files snapshots
        for i in range(5):
            # Reset camera frame index
            self.cameras['main'].current_frame_idx = 0
            
            # Start detection again
            self.detection_manager.start_camera('main')
            
            # Wait for detection to process frames
            time.sleep(2)
            
            # Stop detection
            self.detection_manager.stop_camera('main')
        
        # Wait for cleanup thread to run
        time.sleep(2)
        
        # Count snapshots - should be capped at max_files (5)
        snapshots = [f for f in os.listdir(self.snapshot_dir) if f.endswith('.jpg')]
        self.assertLessEqual(len(snapshots), 5, f"FIFO cleanup failed, found {len(snapshots)} snapshots, expected <= 5")
        
        # Verify the newest snapshots were kept
        # Get timestamps from filenames (assuming format camera_id_TIMESTAMP.jpg)
        timestamps = []
        for snapshot in snapshots:
            # Extract timestamp from filename
            parts = snapshot.split('_')
            if len(parts) >= 3:
                timestamp_parts = parts[2:]  # The rest after camera_id is the timestamp
                timestamp = '_'.join(timestamp_parts).replace('.jpg', '')
                timestamps.append(timestamp)
        
        # Sort timestamps (they should be in descending order if newest kept)
        sorted_timestamps = sorted(timestamps, reverse=True)
        self.assertEqual(timestamps, sorted_timestamps, "FIFO cleanup didn't keep the newest files")

if __name__ == "__main__":
    unittest.main() 