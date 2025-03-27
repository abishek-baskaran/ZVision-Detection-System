#!/usr/bin/env python3
# Test script for detection toggle functionality

import requests
import time
import sys

def main():
    print("Testing detection toggle functionality...")
    
    # Base URL for API
    base_url = "http://localhost:5000"
    
    # Check current status
    try:
        print("\nChecking initial status...")
        response = requests.get(f"{base_url}/api/status")
        status = response.json()
        print(f"Detection active: {status.get('detection_active', 'Unknown')}")
        print(f"Person detected: {status.get('detection', {}).get('person_detected', 'Unknown')}")
    except Exception as e:
        print(f"Error checking status: {e}")
        return
    
    # Toggle detection off
    try:
        print("\nStopping detection...")
        response = requests.post(f"{base_url}/api/detection/stop")
        result = response.json()
        print(f"Response: {result}")
        
        # Check status after stopping
        time.sleep(1)
        response = requests.get(f"{base_url}/api/status")
        status = response.json()
        print(f"Detection active: {status.get('detection_active', 'Unknown')}")
    except Exception as e:
        print(f"Error stopping detection: {e}")
    
    # Wait a bit
    print("\nWaiting 3 seconds...")
    time.sleep(3)
    
    # Toggle detection on
    try:
        print("\nStarting detection...")
        response = requests.post(f"{base_url}/api/detection/start")
        result = response.json()
        print(f"Response: {result}")
        
        # Check status after starting
        time.sleep(1)
        response = requests.get(f"{base_url}/api/status")
        status = response.json()
        print(f"Detection active: {status.get('detection_active', 'Unknown')}")
    except Exception as e:
        print(f"Error starting detection: {e}")
    
    print("\nTest completed. Please check the web interface to verify toggle functionality.")
    print("The web UI should now show detection as active and the toggle button should say 'Pause Detection'.")

if __name__ == "__main__":
    main() 