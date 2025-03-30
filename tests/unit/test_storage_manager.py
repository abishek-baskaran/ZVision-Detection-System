#!/usr/bin/env python3
# Test script for SnapshotStorageManager

import unittest
import os
import time
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import logging

# Import required modules
from managers.storage_manager import SnapshotStorageManager, start_snapshot_cleanup_thread

class TestStorageManager(unittest.TestCase):
    """Test case for SnapshotStorageManager FIFO functionality"""
    
    def setUp(self):
        """Set up test environment before each test"""
        # Create a temporary directory for test snapshots
        self.temp_dir = tempfile.mkdtemp()
        self.snapshot_dir = os.path.join(self.temp_dir, "snapshots")
        os.makedirs(self.snapshot_dir, exist_ok=True)
        
        # Disable logging output during tests
        logging.disable(logging.CRITICAL)
        
        # Create test snapshot files with controlled creation times
        self.test_files = []
        for i in range(30):
            filename = os.path.join(self.snapshot_dir, f"camera_test_{i:02d}.jpg")
            with open(filename, 'w') as f:
                f.write(f"Test snapshot {i}")
            self.test_files.append(filename)
            # Set access/modified time to ensure proper order
            os.utime(filename, (time.time() - (30 - i), time.time() - (30 - i)))
            
    def tearDown(self):
        """Clean up after each test"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Re-enable logging
        logging.disable(logging.NOTSET)
    
    def test_enforce_fifo_basic(self):
        """Test that enforce_fifo deletes oldest files when max_files is exceeded"""
        # Initialize storage manager with max_files=20
        storage_manager = SnapshotStorageManager(directory=self.snapshot_dir, max_files=20)
        
        # Initially we have 30 files
        initial_count = len(os.listdir(self.snapshot_dir))
        self.assertEqual(initial_count, 30)
        
        # Run FIFO enforcement
        storage_manager.enforce_fifo()
        
        # Should have exactly 20 files left
        remaining_count = len(os.listdir(self.snapshot_dir))
        self.assertEqual(remaining_count, 20)
        
        # The oldest 10 files should be deleted
        for i in range(10):
            filename = os.path.join(self.snapshot_dir, f"camera_test_{i:02d}.jpg")
            self.assertFalse(os.path.exists(filename), f"File {filename} should have been deleted")
        
        # The newest 20 files should remain
        for i in range(10, 30):
            filename = os.path.join(self.snapshot_dir, f"camera_test_{i:02d}.jpg")
            self.assertTrue(os.path.exists(filename), f"File {filename} should still exist")
    
    def test_enforce_fifo_under_limit(self):
        """Test that enforce_fifo doesn't delete files when under the limit"""
        # Initialize storage manager with max_files=50 (more than we have)
        storage_manager = SnapshotStorageManager(directory=self.snapshot_dir, max_files=50)
        
        # Run FIFO enforcement
        storage_manager.enforce_fifo()
        
        # Should still have all 30 files
        remaining_count = len(os.listdir(self.snapshot_dir))
        self.assertEqual(remaining_count, 30)
        
        # Check all files still exist
        for i in range(30):
            filename = os.path.join(self.snapshot_dir, f"camera_test_{i:02d}.jpg")
            self.assertTrue(os.path.exists(filename), f"File {filename} should still exist")
    
    def test_enforce_fifo_edge_case(self):
        """Test enforce_fifo with edge cases (max_files=1, empty directory)"""
        # Test with max_files=1
        storage_manager = SnapshotStorageManager(directory=self.snapshot_dir, max_files=1)
        
        # Run FIFO enforcement
        storage_manager.enforce_fifo()
        
        # Should have exactly 1 file left (the newest one)
        remaining_count = len(os.listdir(self.snapshot_dir))
        self.assertEqual(remaining_count, 1)
        
        # Check only the newest file exists
        newest_file = os.path.join(self.snapshot_dir, f"camera_test_29.jpg")
        self.assertTrue(os.path.exists(newest_file), f"Newest file should still exist")
        
        # Now test with empty directory
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir, exist_ok=True)
        
        storage_manager = SnapshotStorageManager(directory=empty_dir, max_files=10)
        
        # Run FIFO enforcement (should not raise any errors)
        storage_manager.enforce_fifo()
    
    @patch('threading.Thread')
    def test_cleanup_thread(self, mock_thread):
        """Test that the cleanup thread is started correctly"""
        # Call the thread starter function
        thread = start_snapshot_cleanup_thread(
            directory=self.snapshot_dir,
            max_files=25,
            interval=30
        )
        
        # Verify thread was created and started
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        
        # Verify the thread was created as a daemon
        thread_kwargs = mock_thread.call_args.kwargs
        self.assertTrue(thread_kwargs['daemon'])
        
        # The target function should be a callable
        self.assertTrue(callable(thread_kwargs['target']))
    
    def test_directory_creation(self):
        """Test that the snapshots directory is created if it doesn't exist"""
        # Create a non-existent directory path
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent_dir")
        
        # Verify directory doesn't exist
        self.assertFalse(os.path.exists(nonexistent_dir))
        
        # Initialize storage manager
        storage_manager = SnapshotStorageManager(directory=nonexistent_dir, max_files=10)
        
        # Directory should now exist
        self.assertTrue(os.path.exists(nonexistent_dir))
        
if __name__ == "__main__":
    unittest.main() 