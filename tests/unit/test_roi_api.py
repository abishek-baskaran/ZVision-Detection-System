#!/usr/bin/env python3
# Unit tests for ROI configuration API endpoints

import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from managers.resource_provider import ResourceProvider
from managers.camera_manager import CameraManager
from managers.dashboard_manager import DashboardManager
from managers.database_manager import DatabaseManager
from managers.detection_manager import DetectionManager
from managers.api_manager import APIManager

class TestROIConfigurationAPI(unittest.TestCase):
    """
    Unit tests for ROI configuration API endpoints.
    """
    
    def setUp(self):
        """Set up the test environment"""
        # Create mock objects
        self.resource_provider = MagicMock()
        self.camera_manager = MagicMock()
        self.dashboard_manager = MagicMock()
        self.db_manager = MagicMock()
        self.detection_manager = MagicMock()
        
        # Set up necessary methods on the mock objects
        self.resource_provider.get_logger.return_value = MagicMock()
        self.resource_provider.get_config.return_value = {
            'api': {'host': '127.0.0.1', 'port': 5000}
        }
        self.detection_manager.get_roi.return_value = None
        self.detection_manager.get_entry_direction.return_value = None
        self.detection_manager.is_running = True
        
        # Create the API manager with mock dependencies
        self.api_manager = APIManager(
            self.resource_provider,
            self.camera_manager,
            self.detection_manager,
            self.dashboard_manager,
            self.db_manager
        )
        
        # Create a test client
        self.app = self.api_manager.app.test_client()
    
    def test_set_roi_endpoint(self):
        """Test the endpoint for setting ROI configuration"""
        # Test data
        test_roi = {
            'x1': 100,
            'y1': 100,
            'x2': 300,
            'y2': 300,
            'entry_direction': 'LTR'
        }
        
        # Make request to set ROI
        response = self.app.post(
            '/api/cameras/0/roi',
            data=json.dumps(test_roi),
            content_type='application/json'
        )
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Verify detection manager methods were called
        self.detection_manager.set_roi.assert_called_once_with((100, 100, 300, 300))
        self.detection_manager.set_entry_direction.assert_called_once_with('LTR')
    
    def test_clear_roi_endpoint(self):
        """Test the endpoint for clearing ROI configuration"""
        # Make request to clear ROI
        response = self.app.post('/api/cameras/0/roi/clear')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        
        # Verify detection manager method was called
        self.detection_manager.clear_roi.assert_called_once()
    
    def test_status_includes_roi(self):
        """Test that the status endpoint includes ROI information"""
        # Set up mock return values for get_roi and get_entry_direction
        self.detection_manager.get_roi.return_value = (100, 100, 300, 300)
        self.detection_manager.get_entry_direction.return_value = 'LTR'
        
        # Mock the get_detection_status method
        self.detection_manager.get_detection_status.return_value = {
            'person_detected': False,
            'last_detection_time': None,
            'direction': 'unknown'
        }
        
        # Mock the get_summary method
        self.dashboard_manager.get_summary.return_value = {
            'detection_count': 0,
            'direction_counts': {'left_to_right': 0, 'right_to_left': 0, 'unknown': 0}
        }
        
        # Make request to status endpoint
        response = self.app.get('/api/status')
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Check ROI information in response
        self.assertIn('roi', data)
        self.assertIn('coords', data['roi'])
        self.assertIn('entry_direction', data['roi'])
        
        # Verify ROI coordinates
        coords = data['roi']['coords']
        self.assertEqual(coords['x1'], 100)
        self.assertEqual(coords['y1'], 100)
        self.assertEqual(coords['x2'], 300)
        self.assertEqual(coords['y2'], 300)
        
        # Verify entry direction
        self.assertEqual(data['roi']['entry_direction'], 'LTR')

if __name__ == '__main__':
    unittest.main() 