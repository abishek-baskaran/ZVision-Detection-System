#!/usr/bin/env python3
# Unit tests for analytics engine functionality

import unittest
import os
import sqlite3
import json
import tempfile
from unittest import mock

# Import the module to test
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from managers import analytics_engine

class TestAnalyticsEngine(unittest.TestCase):
    """
    Test cases for the analytics engine
    """
    
    def setUp(self):
        """
        Set up a test database and initialize the analytics engine
        """
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Initialize the database with test schema and data
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create detection_events table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detection_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                direction TEXT
            )
        ''')
        
        # Insert some test detection events
        test_data = [
            ('main', 'entry', '2025-03-29 10:00:00', 'left_to_right'),
            ('main', 'exit', '2025-03-29 11:00:00', 'right_to_left'),
            ('secondary', 'entry', '2025-03-29 10:30:00', 'left_to_right'),
            ('secondary', 'entry', '2025-03-29 11:30:00', 'left_to_right'),
            ('test_camera', 'exit', '2025-03-29 09:00:00', 'right_to_left'),
            ('test_camera', 'entry', '2025-03-29 09:15:00', 'left_to_right'),
            ('test_camera', 'entry', '2025-03-29 09:30:00', 'left_to_right'),
        ]
        
        for event in test_data:
            cursor.execute(
                "INSERT INTO detection_events (camera_id, event_type, timestamp, direction) VALUES (?, ?, ?, ?)",
                event
            )
        
        conn.commit()
        conn.close()
        
        # Initialize the analytics engine with our test database
        config = {'database': {'path': self.db_path}}
        analytics_engine.init(config)
    
    def tearDown(self):
        """
        Clean up test database
        """
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_get_camera_entry_counts(self):
        """
        Test that the get_camera_entry_counts function returns the correct counts
        """
        # Create a mock camera registry
        mock_camera = mock.MagicMock()
        mock_registry = mock.MagicMock()
        mock_registry.get_all_cameras.return_value = {
            'main': mock_camera,
            'secondary': mock_camera,
            'test_camera': mock_camera
        }
        
        # Get camera entry counts from the last 24 hours
        counts = analytics_engine.get_camera_entry_counts(
            last_hours=24,
            camera_registry=mock_registry
        )
        
        # Check that all cameras have counts
        self.assertIn('main', counts)
        self.assertIn('secondary', counts)
        self.assertIn('test_camera', counts)
        
        # Check that the counts match our test data
        # main: 1 entry + 1 exit = 2
        # secondary: 2 entries = 2
        # test_camera: 1 exit + 2 entries = 3
        self.assertEqual(counts['main'], 2)
        self.assertEqual(counts['secondary'], 2)
        self.assertEqual(counts['test_camera'], 3)
    
    def test_get_time_series_all_cameras(self):
        """
        Test that the get_time_series function returns data for all cameras
        """
        # Create a mock camera registry
        mock_camera = mock.MagicMock()
        mock_registry = mock.MagicMock()
        mock_registry.get_all_cameras.return_value = {
            'main': mock_camera,
            'secondary': mock_camera,
            'test_camera': mock_camera
        }
        
        # Get time series data for all cameras
        time_series = analytics_engine.get_time_series(
            camera_id=None,
            hours=24,
            camera_registry=mock_registry
        )
        
        # Check that all cameras are included
        self.assertIn('main', time_series)
        self.assertIn('secondary', time_series)
        self.assertIn('test_camera', time_series)
        
        # Check format of data for each camera
        for camera_id, data in time_series.items():
            self.assertIsInstance(data, list)
            if data:  # If there's data for this camera
                self.assertIn('hour', data[0])
                self.assertIn('count', data[0])
    
    def test_get_time_series_specific_camera(self):
        """
        Test that the get_time_series function returns data for a specific camera
        """
        # Get time series data for just the main camera
        time_series = analytics_engine.get_time_series(
            camera_id='main',
            hours=24
        )
        
        # Check the format of the returned data
        self.assertIsInstance(time_series, list)
        
        # There should be at least some data points
        self.assertGreater(len(time_series), 0)
        
        # Check the format of each data point
        for point in time_series:
            self.assertIn('hour', point)
            self.assertIn('count', point)
    
    def test_get_heatmap(self):
        """
        Test that the get_heatmap function returns a properly formatted heatmap
        """
        width, height = 10, 10
        heatmap = analytics_engine.get_heatmap(
            camera_id='main',
            width=width,
            height=height
        )
        
        # Check that the heatmap has the right dimensions
        self.assertEqual(len(heatmap), height)
        self.assertEqual(len(heatmap[0]), width)
        
        # Check that the heatmap contains numeric values
        for row in heatmap:
            for value in row:
                self.assertIsInstance(value, int)
                
        # Verify that there are some non-zero values (should be for visual interest)
        flat_map = [value for row in heatmap for value in row]
        non_zero_count = sum(1 for value in flat_map if value > 0)
        self.assertGreater(non_zero_count, 0)

if __name__ == '__main__':
    unittest.main() 