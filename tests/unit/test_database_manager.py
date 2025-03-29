#!/usr/bin/env python3
# Test script for DatabaseManager

from managers.resource_provider import ResourceProvider
from managers.database_manager import DatabaseManager

def main():
    # Initialize ResourceProvider
    rp = ResourceProvider("config.yaml")
    
    # Get a logger for this test
    logger = rp.get_logger()
    logger.info("Starting DatabaseManager test")
    
    # Initialize DatabaseManager
    db = DatabaseManager(rp)
    
    # Test logging an event
    logger.info("Testing log_event")
    test_event_data = {"foo": "bar", "test": True, "value": 123}
    success = db.log_event("test_event", test_event_data)
    logger.info(f"Event logging successful: {success}")
    
    # Get recent events
    logger.info("Testing get_events")
    events = db.get_events(10)
    
    # Print events
    logger.info(f"Retrieved {len(events)} events")
    for event in events:
        logger.info(f"Event ID: {event['id']}, Type: {event['type']}, Timestamp: {event['timestamp']}")
        logger.info(f"Event Data: {event['data']}")
    
    logger.info("DatabaseManager test completed")

if __name__ == "__main__":
    main() 