#!/usr/bin/env python3
# Manual test for snapshot functionality

import os
import sys
import time
import logging
import shutil
from datetime import datetime
import cv2
import numpy as np

# Add the parent directory to the system path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from managers.resource_provider import ResourceProvider
from managers.storage_manager import SnapshotStorageManager, start_snapshot_cleanup_thread
from managers.database_manager import DatabaseManager

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SnapshotTest")

def create_test_snapshot(directory, camera_id, index):
    """Create a test snapshot with visible index number"""
    # Create a blank frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Add timestamp and index
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"Snapshot #{index}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    cv2.putText(frame, timestamp, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(frame, f"Camera: {camera_id}", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Draw a rectangle with different color for each snapshot
    color = ((index * 40) % 255, (index * 80) % 255, (index * 120) % 255)
    cv2.rectangle(frame, (200, 200), (400, 400), color, -1)
    
    # Generate filename
    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{directory}/camera_{camera_id}_{timestamp_file}.jpg"
    
    # Save the image
    cv2.imwrite(filename, frame)
    logger.info(f"Created test snapshot: {filename}")
    
    return filename

def test_snapshot_capture():
    """Test snapshot capture functionality"""
    logger.info("Starting snapshot capture test")
    
    # Create temporary snapshot directory
    snapshot_dir = "snapshots_test"
    if os.path.exists(snapshot_dir):
        shutil.rmtree(snapshot_dir)
    os.makedirs(snapshot_dir, exist_ok=True)
    
    # Capture test snapshots
    camera_ids = ["main", "secondary", "test_camera"]
    snapshots = []
    
    logger.info(f"Capturing test snapshots in {snapshot_dir}")
    for camera_id in camera_ids:
        for i in range(5):
            snapshot_path = create_test_snapshot(snapshot_dir, camera_id, i)
            snapshots.append(snapshot_path)
            time.sleep(0.1)  # Small delay to ensure different timestamps
    
    logger.info(f"Created {len(snapshots)} test snapshots")
    
    # Verify files exist
    for snapshot in snapshots:
        assert os.path.exists(snapshot), f"Snapshot {snapshot} does not exist"
    
    logger.info("All snapshots verified")
    return snapshots, snapshot_dir

def test_database_integration(snapshots, db_path="test_snapshot.db"):
    """Test database integration with snapshot paths"""
    logger.info("Testing database integration")
    
    # Ensure the database path is absolute and the directory exists
    db_path = os.path.abspath(db_path)
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        
    logger.info(f"Using database at: {db_path}")
    
    # Initialize ResourceProvider with mock config
    class MockResourceProvider:
        def get_config(self):
            return {
                'database': {
                    'path': db_path
                }
            }
        
        def get_logger(self, *args, **kwargs):
            return logger
    
    rp = MockResourceProvider()
    
    # Initialize database manager
    db_manager = DatabaseManager(rp)
    
    # Log some test detection events with snapshots
    event_types = ["detection_start", "detection_end", "entry", "exit"]
    directions = ["left_to_right", "right_to_left", "unknown"]
    
    logger.info("Logging test detection events to database")
    for i, snapshot in enumerate(snapshots):
        # Extract camera_id from filename (format: snapshots_test/camera_[camera_id]_timestamp.jpg)
        parts = os.path.basename(snapshot).split('_')
        camera_id = parts[1] if len(parts) >= 2 else "unknown"
        
        event_type = event_types[i % len(event_types)]
        direction = directions[i % len(directions)]
        
        db_manager.log_detection_event(
            event_type=event_type,
            direction=direction,
            camera_id=camera_id,
            snapshot_path=snapshot
        )
    
    # Query the database to verify events were logged
    events = db_manager.get_recent_detection_events(limit=len(snapshots) + 5)
    logger.info(f"Retrieved {len(events)} events from database")
    
    # Verify snapshots are in the database
    snapshot_paths_in_db = [e['snapshot_path'] for e in events if 'snapshot_path' in e]
    logger.info(f"Found {len(snapshot_paths_in_db)} snapshot paths in database")
    
    # Show some sample events
    for i, event in enumerate(events[:5]):
        logger.info(f"Event {i+1}: {event['event_type']} | Camera: {event['camera_id']} | Snapshot: {event['snapshot_path']}")
    
    return db_manager

def test_fifo_cleanup(snapshot_dir, max_files=10):
    """Test FIFO cleanup of snapshots"""
    logger.info(f"Testing FIFO cleanup with max_files={max_files}")
    
    # Count initial snapshots
    initial_count = len([f for f in os.listdir(snapshot_dir) if f.endswith('.jpg')])
    logger.info(f"Initial snapshot count: {initial_count}")
    
    # Initialize storage manager with a low max_files
    storage_manager = SnapshotStorageManager(directory=snapshot_dir, max_files=max_files, logger=logger)
    
    # Run FIFO enforcement
    logger.info("Running FIFO enforcement")
    storage_manager.enforce_fifo()
    
    # Count remaining snapshots
    remaining_count = len([f for f in os.listdir(snapshot_dir) if f.endswith('.jpg')])
    logger.info(f"Remaining snapshot count: {remaining_count}")
    
    # Verify count
    assert remaining_count <= max_files, f"Expected at most {max_files} snapshots, found {remaining_count}"
    if initial_count > max_files:
        assert remaining_count == max_files, f"Expected exactly {max_files} snapshots, found {remaining_count}"
    
    # List remaining snapshots
    remaining_snapshots = sorted([f for f in os.listdir(snapshot_dir) if f.endswith('.jpg')])
    if remaining_snapshots:
        logger.info(f"Remaining snapshots: {', '.join(remaining_snapshots[:5])}")
    
    return storage_manager

def main():
    """Main test function"""
    logger.info("=== Starting Snapshot Functionality Test ===")
    
    snapshot_dir = None
    
    try:
        # Test snapshot capture
        snapshots, snapshot_dir = test_snapshot_capture()
        
        # Test database integration
        db_manager = test_database_integration(snapshots)
        
        # Test FIFO cleanup
        storage_manager = test_fifo_cleanup(snapshot_dir, max_files=10)
        
        # Create more snapshots to test cleanup again
        logger.info("Creating additional snapshots to test cleanup again")
        for i in range(5):
            create_test_snapshot(snapshot_dir, "main", i + 100)
        
        # Run cleanup again
        logger.info("Running cleanup again")
        storage_manager.enforce_fifo()
        
        # Show final results
        final_count = len([f for f in os.listdir(snapshot_dir) if f.endswith('.jpg')])
        logger.info(f"Final snapshot count: {final_count}")
        
        logger.info("=== Snapshot Functionality Test Completed Successfully ===")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        # Clean up (comment out to keep test files for inspection)
        if snapshot_dir and os.path.exists(snapshot_dir):
            logger.info(f"Cleaning up {snapshot_dir}")
            shutil.rmtree(snapshot_dir)
        
        if os.path.exists("test_snapshot.db"):
            logger.info("Cleaning up test database")
            os.remove("test_snapshot.db")

if __name__ == "__main__":
    main() 