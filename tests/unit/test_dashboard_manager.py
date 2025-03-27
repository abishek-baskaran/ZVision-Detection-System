#!/usr/bin/env python3
# Test script for DashboardManager

from managers.resource_provider import ResourceProvider
from managers.dashboard_manager import DashboardManager
import time

def main():
    # Initialize ResourceProvider
    rp = ResourceProvider("config.yaml")
    
    # Get a logger for this test
    logger = rp.get_logger("TestDashboardManager")
    logger.info("Starting DashboardManager test")
    
    # Initialize DashboardManager (without detection_manager for simple testing)
    dashboard = DashboardManager(rp)
    
    # Test initial state
    logger.info("Initial dashboard summary:")
    logger.info(dashboard.get_summary())
    
    # Simulate some detections
    logger.info("Simulating detections...")
    
    # Record several detections with different directions
    dashboard.record_detection()
    dashboard.record_direction("left_to_right")
    time.sleep(0.5)
    
    dashboard.record_detection()
    dashboard.record_direction("right_to_left")
    time.sleep(0.5)
    
    dashboard.record_detection()
    dashboard.record_direction("left_to_right")
    time.sleep(0.5)
    
    dashboard.record_detection()
    dashboard.record_direction("unknown")
    
    # Get updated summary
    logger.info("Updated dashboard summary:")
    logger.info(dashboard.get_summary())
    
    # Test hourly metrics
    logger.info("Hourly metrics:")
    logger.info(dashboard.get_hourly_metrics(hours=1))
    
    # Test recent detections
    logger.info("Recent detections:")
    logger.info(dashboard.get_recent_detections(count=5))
    
    logger.info("DashboardManager test completed")

if __name__ == "__main__":
    main() 