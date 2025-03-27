#!/usr/bin/env python3
# Test script for main.py

import subprocess
import time
import os
import signal
import requests
import sys

def main():
    print("Starting ZVision system test...")
    
    # Start the main process
    process = subprocess.Popen(
        ["python", "main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    print("Main process started. PID:", process.pid)
    print("Waiting 10 seconds for system to initialize...")
    time.sleep(10)
    
    # Check if process is still running
    if process.poll() is not None:
        print("ERROR: Main process has terminated unexpectedly!")
        stdout, stderr = process.communicate()
        print("STDOUT:", stdout.decode())
        print("STDERR:", stderr.decode())
        return 1
    
    # Test API endpoints
    print("\nTesting API endpoints...")
    test_endpoints(["http://localhost:5000/", 
                   "http://localhost:5000/api/status",
                   "http://localhost:5000/api/events",
                   "http://localhost:5000/api/metrics",
                   "http://localhost:5000/api/frame/current"])
    
    # Terminate the process
    print("\nTest completed. Stopping main process...")
    try:
        process.send_signal(signal.SIGINT)  # Send CTRL+C
        process.wait(timeout=5)  # Wait for process to terminate
        print("Main process terminated gracefully.")
    except subprocess.TimeoutExpired:
        print("Process didn't terminate within timeout, forcing kill...")
        process.kill()
    
    return 0

def test_endpoints(endpoints):
    for endpoint in endpoints:
        try:
            print(f"Testing {endpoint}...", end=" ")
            response = requests.get(endpoint, timeout=2)
            if response.status_code == 200:
                print(f"SUCCESS (Status: {response.status_code})")
            else:
                print(f"FAIL (Status: {response.status_code})")
        except requests.RequestException as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    sys.exit(main()) 