#!/usr/bin/env python3
# Test script for dashboard analytics

import requests
import time
import json
from datetime import datetime, timedelta

def print_json(data):
    """Print JSON data in a readable format"""
    print(json.dumps(data, indent=4))

def main():
    print("Testing Dashboard Analytics")
    print("==========================")
    
    base_url = "http://localhost:5000"
    
    # Test 1: Check current status and metrics
    print("\n1. Current System Status:")
    try:
        response = requests.get(f"{base_url}/api/status")
        status = response.json()
        print_json(status)
    except Exception as e:
        print(f"Error fetching status: {e}")
    
    # Test 2: Get metrics
    print("\n2. Current Metrics:")
    try:
        response = requests.get(f"{base_url}/api/metrics")
        metrics = response.json()
        print("Footfall Count:", metrics.get("footfall_count", "N/A"))
        print("Direction Counts:", metrics.get("total", {}).get("direction_counts", {}))
        
        # Print hourly metrics summary if available
        hourly = metrics.get("hourly", {})
        if hourly:
            print(f"\nHourly Metrics: {len(hourly)} hours recorded")
            # Get the most recent hour
            latest_hour = max(hourly.keys()) if hourly else None
            if latest_hour:
                print(f"Latest hour ({latest_hour}):")
                print_json(hourly[latest_hour])
    except Exception as e:
        print(f"Error fetching metrics: {e}")
    
    # Test 3: Get daily metrics
    print("\n3. Daily Metrics:")
    try:
        response = requests.get(f"{base_url}/api/metrics/daily")
        daily = response.json()
        if daily:
            days = len(daily)
            print(f"Daily data available for {days} day(s)")
            
            # Sort dates in descending order
            sorted_dates = sorted(daily.keys(), reverse=True)
            
            for date in sorted_dates:
                day_data = daily[date]
                print(f"\nDate: {date}")
                print(f"  Footfall Count: {day_data.get('detection_count', 0)}")
                print(f"  Left to Right: {day_data.get('left_to_right', 0)}")
                print(f"  Right to Left: {day_data.get('right_to_left', 0)}")
        else:
            print("No daily metrics available yet")
    except Exception as e:
        print(f"Error fetching daily metrics: {e}")
    
    # Test 4: Get recent detections
    print("\n4. Recent Detections:")
    try:
        response = requests.get(f"{base_url}/api/detections/recent")
        detections = response.json()
        if detections:
            print(f"Found {len(detections)} recent detection(s)")
            for idx, detection in enumerate(detections):
                print(f"\nDetection #{idx+1}:")
                print(f"  Timestamp: {detection.get('timestamp', 'N/A')}")
                print(f"  Type: {detection.get('event_type', 'N/A')}")
                print(f"  Direction: {detection.get('direction', 'N/A')}")
        else:
            print("No recent detections found")
    except Exception as e:
        print(f"Error fetching recent detections: {e}")
    
    print("\nTest completed!")

if __name__ == "__main__":
    main() 