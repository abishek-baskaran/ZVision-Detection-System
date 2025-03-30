#!/usr/bin/env python3
# Storage Manager - Handles automatic cleanup of snapshot files

import os
import time
import threading
from pathlib import Path
import logging

class SnapshotStorageManager:
    """
    Manages storage of snapshot files using a FIFO approach
    Automatically deletes the oldest files when the maximum number is exceeded
    """
    
    def __init__(self, directory="snapshots", max_files=1000, logger=None):
        """
        Initialize the storage manager
        
        Args:
            directory: Directory where snapshots are stored
            max_files: Maximum number of files to keep
            logger: Optional logger instance
        """
        self.directory = Path(directory)
        self.max_files = max_files
        
        # Create directory if it doesn't exist
        if not self.directory.exists():
            self.directory.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        self.logger = logger or logging.getLogger(__name__)
        
        self.logger.info(f"SnapshotStorageManager initialized with max files: {max_files}")
    
    def enforce_fifo(self):
        """
        Delete the oldest files if the maximum number is exceeded
        """
        try:
            # Check if directory exists
            if not self.directory.exists():
                self.logger.warning(f"Snapshot directory {self.directory} does not exist")
                return
            
            # Get all jpg files in the directory
            files = list(self.directory.glob("*.jpg"))
            
            # Check if we need to delete any files
            if len(files) <= self.max_files:
                return
            
            # Sort files by modification time (oldest first)
            files.sort(key=lambda x: os.path.getmtime(str(x)))
            
            # Calculate how many files to delete
            num_to_delete = len(files) - self.max_files
            files_to_delete = files[:num_to_delete]
            
            # Delete the oldest files
            for file in files_to_delete:
                try:
                    os.remove(str(file))
                    self.logger.info(f"Deleted snapshot: {file}")
                except Exception as e:
                    self.logger.error(f"Failed to delete {file}: {e}")
            
            remaining = len(files) - len(files_to_delete)
            self.logger.info(f"FIFO cleanup completed: deleted {len(files_to_delete)} files, remaining: {remaining}")
            
        except Exception as e:
            self.logger.error(f"Error in enforce_fifo: {e}")

def start_snapshot_cleanup_thread(directory="snapshots", max_files=1000, interval=3600, logger=None):
    """
    Start a daemon thread for periodic snapshot cleanup
    
    Args:
        directory: Directory where snapshots are stored
        max_files: Maximum number of files to keep
        interval: Cleanup interval in seconds
        logger: Optional logger instance
    
    Returns:
        threading.Thread: The started daemon thread
    """
    logger = logger or logging.getLogger(__name__)
    
    def periodic_snapshot_cleanup():
        storage_manager = SnapshotStorageManager(directory, max_files, logger)
        logger.info(f"Starting periodic snapshot cleanup (interval: {interval}s, max files: {max_files})")
        
        while True:
            try:
                # Run FIFO cleanup
                storage_manager.enforce_fifo()
                
                # Sleep until next cleanup
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"Error in periodic cleanup thread: {e}")
                # Sleep a bit to avoid tight loop in case of recurring errors
                time.sleep(60)
    
    # Create and start the daemon thread
    thread = threading.Thread(target=periodic_snapshot_cleanup, daemon=True)
    thread.name = "snapshot-cleanup"
    thread.start()
    
    logger.info("Snapshot cleanup thread started")
    return thread

if __name__ == "__main__":
    # Simple test code for when run directly
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("SnapshotTest")
    
    # Start cleanup with a short interval for testing
    start_snapshot_cleanup_thread(max_files=100, interval=10, logger=logger)
    
    logger.info("Test mode: Cleanup thread started, press Ctrl+C to exit")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Test mode: Exiting") 