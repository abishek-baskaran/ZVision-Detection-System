#!/usr/bin/env python3
# Test script for Snapshot API functionality

import unittest
import os
import json
from unittest.mock import MagicMock, patch
import tempfile
import shutil

# Import required modules
from managers.resource_provider import ResourceProvider
from managers.api_manager import APIManager

class TestSnapshotAPI(unittest.TestCase):
    """Test case for snapshot API endpoints"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a temporary directory for snapshots
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = os.path.join(self.temp_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        # Create some test snapshot files
        self.create_test_snapshots()
        
        # Mock dependencies
        self.mock_rp = MagicMock()
        self.mock_rp.get_logger.return_value = MagicMock()
        self.mock_rp.get_config.return_value = {
            'api': {
                'host': '127.0.0.1',
                'port': 5000,
                'debug': False
            }
        }
        
        self.mock_camera_manager = MagicMock()
        self.mock_detection_manager = MagicMock()
        self.mock_dashboard_manager = MagicMock()
        self.mock_db_manager = MagicMock()
        self.mock_camera_registry = MagicMock()
        
        # Set up mock database query results for get_camera_snapshots
        self.mock_db_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_db_manager._get_connection.return_value = self.mock_db_conn
        self.mock_db_conn.cursor.return_value = self.mock_cursor
        
        # Mock query results with sample snapshot data
        self.mock_cursor.fetchall.return_value = [
            (1, '2023-01-01 12:00:00', 'detection_start', 'left_to_right', f'{self.snapshot_dir}/camera_main_20230101_120000.jpg'),
            (2, '2023-01-01 12:01:00', 'detection_end', 'left_to_right', f'{self.snapshot_dir}/camera_main_20230101_120100.jpg')
        ]
        
        # Initialize the API manager
        self.api_manager = APIManager(
            self.mock_rp,
            self.mock_camera_manager,
            self.mock_detection_manager,
            self.mock_dashboard_manager,
            self.mock_db_manager,
            self.mock_camera_registry
        )
        
        # Create a test client
        self.app = self.api_manager.app.test_client()
        
    def tearDown(self):
        """Clean up after each test"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def create_test_snapshots(self):
        """Create test snapshot files in the temporary directory"""
        # Create some test snapshot files
        snapshot_paths = [
            os.path.join(self.snapshot_dir, "camera_main_20230101_120000.jpg"),
            os.path.join(self.snapshot_dir, "camera_main_20230101_120100.jpg"),
            os.path.join(self.snapshot_dir, "camera_secondary_20230101_120200.jpg")
        ]
        
        for path in snapshot_paths:
            with open(path, 'w') as f:
                f.write("Test snapshot data")
    
    def test_get_camera_snapshots_endpoint(self):
        """Test the /api/snapshots/<camera_id> endpoint"""
        # Test with valid camera ID
        self.mock_camera_registry.get_camera.return_value = MagicMock()
        
        # Make request
        response = self.app.get('/api/snapshots/main')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Verify response structure
        self.assertEqual(data['camera_id'], 'main')
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['snapshots']), 2)
        
        # Verify snapshot details
        snapshot1 = data['snapshots'][0]
        self.assertEqual(snapshot1['id'], 1)
        self.assertEqual(snapshot1['event_type'], 'detection_start')
        self.assertEqual(snapshot1['direction'], 'left_to_right')
        self.assertTrue('snapshot_path' in snapshot1)
        
        # Verify database query was called correctly
        self.mock_cursor.execute.assert_called_once()
        call_args = self.mock_cursor.execute.call_args[0]
        self.assertIn('camera_id = ?', call_args[0])
        self.assertEqual(call_args[1][0], 'main')
    
    def test_get_camera_snapshots_invalid_camera(self):
        """Test the /api/snapshots/<camera_id> endpoint with invalid camera"""
        # Set up mock to return None for non-existent camera
        self.mock_camera_registry.get_camera.return_value = None
        
        # Make request
        response = self.app.get('/api/snapshots/nonexistent')
        
        # Check response - should be 404
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertTrue('error' in data)
    
    @patch('os.path.abspath')
    @patch('flask.send_from_directory')
    def test_get_snapshot_image_valid(self, mock_send, mock_abspath):
        """Test the /api/snapshot/image/<path> endpoint with valid path"""
        # Set up path mocks
        mock_abspath.side_effect = lambda p: p  # Return the input unchanged
        mock_send.return_value = "Mock image response"
        
        # Make request with valid relative path
        response = self.app.get('/api/snapshot/image/camera_main_20230101_120000.jpg')
        
        # Check that send_from_directory was called
        mock_send.assert_called_once()
        self.assertEqual(response.status_code, 200)
    
    @patch('os.path.abspath')
    def test_get_snapshot_image_invalid_path(self, mock_abspath):
        """Test the /api/snapshot/image/<path> endpoint with invalid path"""
        # Set up path mocks for an invalid path (tries to access outside snapshot dir)
        mock_abspath.side_effect = lambda p: p.replace('snapshots', '/tmp')
        
        # Make request with invalid relative path
        response = self.app.get('/api/snapshot/image/../../../etc/passwd')
        
        # Should get 403 Forbidden
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.data)
        self.assertTrue('error' in data)
    
    @patch('os.path.exists')
    def test_get_snapshot_image_nonexistent(self, mock_exists):
        """Test the /api/snapshot/image/<path> endpoint with non-existent file"""
        # Set up mock to indicate file doesn't exist
        mock_exists.return_value = False
        
        # Make request with non-existent file
        response = self.app.get('/api/snapshot/image/camera_main_nonexistent.jpg')
        
        # Should get 404 Not Found
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.data)
        self.assertTrue('error' in data)

if __name__ == "__main__":
    unittest.main() 