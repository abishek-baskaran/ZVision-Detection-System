#!/usr/bin/env python3
# Test script for ResourceProvider

from managers.resource_provider import ResourceProvider
import os

def main():
    # Create ResourceProvider instance
    print("Creating ResourceProvider instance...")
    rp = ResourceProvider("config.yaml")
    
    # Test config loading
    print("\nTesting config loading...")
    config = rp.get_config()
    print(f"Camera device ID: {config.get('camera', {}).get('device_id')}")
    print(f"Frame width: {config.get('camera', {}).get('width')}")
    print(f"Frame height: {config.get('camera', {}).get('height')}")
    print(f"Detection confidence threshold: {config.get('detection', {}).get('confidence_threshold')}")
    
    # Test logging with different loggers
    print("\nTesting logging with different loggers...")
    
    # Test with default logger
    default_logger = rp.get_logger()
    print(f"Default logger name: {default_logger.name}")
    default_logger.debug("This is a DEBUG message from default logger")
    default_logger.info("This is an INFO message from default logger")
    default_logger.warning("This is a WARNING message from default logger")
    default_logger.error("This is an ERROR message from default logger")
    
    # Test with named logger
    test_logger = rp.get_logger("TestLogger")
    print(f"Named logger name: {test_logger.name}")
    test_logger.debug("This is a DEBUG message from TestLogger")
    test_logger.info("This is an INFO message from TestLogger")
    test_logger.warning("This is a WARNING message from TestLogger")
    test_logger.error("This is an ERROR message from TestLogger")
    
    # Verify log file existence
    log_file = config.get('logging', {}).get('file', 'logs/app.log')
    if os.path.exists(log_file):
        print(f"\nLog file created at: {log_file}")
        print(f"Log file size: {os.path.getsize(log_file)} bytes")
    else:
        print(f"\nWarning: Log file not found at {log_file}")

if __name__ == "__main__":
    main() 