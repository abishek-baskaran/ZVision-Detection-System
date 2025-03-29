#!/usr/bin/env python3
# Manual test for analytics endpoints

import requests
import json
import time
import sys
import argparse

def test_analytics_endpoints(host="localhost", port=5000):
    """
    Test the analytics API endpoints
    """
    base_url = f"http://{host}:{port}"
    
    print("\n===== Testing Analytics Endpoints =====\n")
    
    # Test compare endpoint
    print("\n----- Testing /api/analytics/compare endpoint -----")
    try:
        response = requests.get(f"{base_url}/api/analytics/compare")
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Compare endpoint returned 200 OK")
            print(f"Time period: {data.get('time_period', 'N/A')}")
            print(f"Total count: {data.get('total', 'N/A')}")
            print("Camera counts:")
            for camera, count in data.get('camera_counts', {}).items():
                print(f"  - {camera}: {count}")
        else:
            print(f"ERROR: Compare endpoint returned {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"ERROR: Exception when testing compare endpoint: {e}")
    
    # Test time-series endpoint (all cameras)
    print("\n----- Testing /api/analytics/time-series endpoint (all cameras) -----")
    try:
        response = requests.get(f"{base_url}/api/analytics/time-series")
        if response.status_code == 200:
            data = response.json()
            print("SUCCESS: Time-series endpoint returned 200 OK")
            print(f"Time period: {data.get('time_period', 'N/A')}")
            cameras = data.get('data', {}).keys()
            print(f"Available cameras: {', '.join(cameras)}")
            
            # Show sample data for first camera
            if cameras:
                first_camera = list(cameras)[0]
                camera_data = data.get('data', {}).get(first_camera, [])
                print(f"\nSample data for camera '{first_camera}':")
                for i, point in enumerate(camera_data[:5]):  # Show first 5 points
                    print(f"  {i+1}. Hour: {point.get('hour')}, Count: {point.get('count')}")
                if len(camera_data) > 5:
                    print(f"  ... ({len(camera_data)-5} more data points)")
        else:
            print(f"ERROR: Time-series endpoint returned {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"ERROR: Exception when testing time-series endpoint: {e}")
    
    # Test time-series endpoint (specific camera)
    print("\n----- Testing /api/analytics/time-series endpoint (specific camera) -----")
    camera_id = "main"  # Change to a camera ID that exists in your system
    try:
        response = requests.get(f"{base_url}/api/analytics/time-series?camera={camera_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Time-series endpoint for camera '{camera_id}' returned 200 OK")
            print(f"Time period: {data.get('time_period', 'N/A')}")
            
            camera_data = data.get('data', [])
            print(f"\nData points for camera '{camera_id}':")
            for i, point in enumerate(camera_data[:5]):  # Show first 5 points
                print(f"  {i+1}. Hour: {point.get('hour')}, Count: {point.get('count')}")
            if len(camera_data) > 5:
                print(f"  ... ({len(camera_data)-5} more data points)")
        else:
            print(f"ERROR: Time-series endpoint for camera '{camera_id}' returned {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"ERROR: Exception when testing camera-specific time-series endpoint: {e}")
    
    # Test heatmap endpoint
    print("\n----- Testing /api/analytics/heatmap endpoint -----")
    camera_id = "main"  # Change to a camera ID that exists in your system
    try:
        response = requests.get(f"{base_url}/api/analytics/heatmap?camera={camera_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Heatmap endpoint for camera '{camera_id}' returned 200 OK")
            print(f"Camera ID: {data.get('camera_id', 'N/A')}")
            print(f"Dimensions: {data.get('width', 'N/A')} x {data.get('height', 'N/A')}")
            
            heatmap = data.get('heatmap', [])
            if heatmap:
                print("\nHeatmap data (first 3 rows):")
                for i, row in enumerate(heatmap[:3]):
                    print(f"  Row {i+1}: {row[:10]}")
                
                # Find and print hot spots (areas with non-zero values)
                hot_spots = []
                for y, row in enumerate(heatmap):
                    for x, value in enumerate(row):
                        if value > 0:
                            hot_spots.append((x, y, value))
                
                print("\nHot spots (non-zero values):")
                for x, y, value in sorted(hot_spots, key=lambda x: x[2], reverse=True)[:5]:
                    print(f"  Position ({x}, {y}): Value {value}")
        else:
            print(f"ERROR: Heatmap endpoint for camera '{camera_id}' returned {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"ERROR: Exception when testing heatmap endpoint: {e}")
    
    print("\n===== Analytics Endpoints Testing Complete =====\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test ZVision analytics endpoints")
    parser.add_argument("--host", default="localhost", help="Host address (default: localhost)")
    parser.add_argument("--port", default=5000, type=int, help="Port number (default: 5000)")
    
    args = parser.parse_args()
    test_analytics_endpoints(args.host, args.port) 