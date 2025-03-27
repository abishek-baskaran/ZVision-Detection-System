#!/usr/bin/env python3
# Test script for API endpoints

import requests
import json
import time

def print_json(data):
    """Print JSON data in a readable format"""
    print(json.dumps(data, indent=4))

def test_endpoint(base_url, endpoint, method="GET", expected_status=200, params=None, data=None):
    """Test an API endpoint and print results"""
    url = f"{base_url}{endpoint}"
    print(f"\nTesting {method} {url}")
    
    try:
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=data)
        else:
            print(f"Unsupported method: {method}")
            return False
        
        print(f"Status: {response.status_code}")
        if response.status_code != expected_status:
            print(f"ERROR: Expected status {expected_status}, got {response.status_code}")
            return False
        
        # Try to print as JSON if possible
        try:
            print_json(response.json())
        except:
            print("Response is not JSON or is empty")
        
        print("Test passed!")
        return True
    except Exception as e:
        print(f"Error testing endpoint: {e}")
        return False

def main():
    print("Testing API Endpoints")
    print("====================")
    
    base_url = "http://localhost:5000"
    
    # Test all endpoints
    endpoints = [
        # Basic endpoints
        {"url": "/api/status", "method": "GET"},
        {"url": "/api/events", "method": "GET", "params": {"limit": 5}},
        {"url": "/api/detections/recent", "method": "GET", "params": {"count": 5}},
        {"url": "/api/frame/current", "method": "GET"},
        {"url": "/api/settings", "method": "GET"},
        
        # Metrics endpoints
        {"url": "/api/metrics", "method": "GET"},
        {"url": "/api/metrics/daily", "method": "GET"},
        {"url": "/api/metrics/summary", "method": "GET", "params": {"days": 7}},
        
        # Detection control endpoints (these change state, so be careful)
        {"url": "/api/detection/stop", "method": "POST"},
        {"url": "/api/detection/start", "method": "POST"},
    ]
    
    success_count = 0
    for endpoint in endpoints:
        if test_endpoint(
            base_url, 
            endpoint["url"], 
            method=endpoint["method"], 
            params=endpoint.get("params"), 
            data=endpoint.get("data")
        ):
            success_count += 1
        
        # Brief pause to avoid overwhelming the server
        time.sleep(0.5)
    
    print(f"\nSummary: {success_count}/{len(endpoints)} endpoints tested successfully")
    
    # Check video feed (special case - returns a stream)
    print("\nChecking video feed (MJPEG stream)...")
    try:
        response = requests.get(f"{base_url}/video_feed", stream=True, timeout=2)
        # Just check the headers to see if it's a multipart response
        content_type = response.headers.get('Content-Type', '')
        is_mjpeg = 'multipart/x-mixed-replace' in content_type
        
        if is_mjpeg:
            print(f"Video feed working! Content-Type: {content_type}")
            # Close the connection
            response.close()
        else:
            print(f"Video feed not returning proper MJPEG stream. Content-Type: {content_type}")
    except Exception as e:
        print(f"Error checking video feed: {e}")
    
    print("\nAPI endpoint testing complete!")

if __name__ == "__main__":
    main() 