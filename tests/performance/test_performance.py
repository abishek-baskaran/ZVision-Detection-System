#!/usr/bin/env python3
# test_performance.py - Test script for ZVision performance and concurrency

import os
import time
import sqlite3
import psutil
import argparse
import requests
import threading
import logging
import json
import sys
from datetime import datetime

# Add the project root to the Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('zvision-test')

class ZVisionTester:
    def __init__(self, host='localhost', port=5000):
        self.base_url = f"http://{host}:{port}"
        self.api_url = f"{self.base_url}/api"
        
        # Use absolute path to the database from project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
        self.db_path = os.path.join(project_root, "zvision.db")
        
        self.cpu_samples = []
        self.memory_samples = []
        self.response_times = []
        self.process = psutil.Process(os.getpid())
        
        logger.info(f"ZVision Tester initialized for {self.base_url}")
        logger.info(f"Using database at: {self.db_path}")
        
    def get_system_status(self):
        """Get current system status from API"""
        try:
            start = time.time()
            response = requests.get(f"{self.api_url}/status")
            elapsed = time.time() - start
            self.response_times.append(elapsed)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"System status: {json.dumps(data, indent=2)}")
                return data
            else:
                logger.error(f"Failed to get status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return None
    
    def toggle_detection(self, enable=True):
        """Toggle detection on or off"""
        endpoint = f"{self.api_url}/detection/{'start' if enable else 'stop'}"
        try:
            response = requests.post(endpoint)
            if response.status_code == 200:
                logger.info(f"Detection {'enabled' if enable else 'disabled'} successfully")
                return True
            else:
                logger.error(f"Failed to toggle detection: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error toggling detection: {e}")
            return False
    
    def get_recent_metrics(self):
        """Get system metrics from API"""
        try:
            response = requests.get(f"{self.api_url}/metrics")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Total Detections: {data.get('total', {}).get('total_detections', 0)}")
                logger.info(f"Footfall Count: {data.get('footfall_count', 0)}")
                return data
            else:
                logger.error(f"Failed to get metrics: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return None
    
    def get_recent_detections(self, count=5):
        """Get recent detection events from API"""
        try:
            response = requests.get(f"{self.api_url}/detections/recent?count={count}")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Recent detections: {json.dumps(data, indent=2)}")
                return data
            else:
                logger.error(f"Failed to get detections: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting detections: {e}")
            return None
    
    def query_database(self, event_type=None, limit=10):
        """Query the SQLite database for events"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if event_type:
                query = """
                SELECT id, timestamp, event_type, direction, extra_data
                FROM detection_events 
                WHERE event_type = ?
                ORDER BY timestamp DESC LIMIT ?
                """
                cursor.execute(query, (event_type, limit))
            else:
                query = """
                SELECT id, timestamp, event_type, direction, extra_data
                FROM detection_events 
                ORDER BY timestamp DESC LIMIT ?
                """
                cursor.execute(query, (limit,))
            
            results = cursor.fetchall()
            conn.close()
            
            # Format and display results
            if results:
                logger.info(f"Database query results for event_type={event_type}:")
                for row in results:
                    logger.info(f"ID: {row[0]}, Time: {row[1]}, Type: {row[2]}, Direction: {row[3]}")
            else:
                logger.info(f"No database results for event_type={event_type}")
                
            return results
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return []
    
    def monitor_resources(self, duration=10, interval=1.0):
        """Monitor CPU and memory usage for specified duration"""
        logger.info(f"Starting resource monitoring for {duration} seconds...")
        
        end_time = time.time() + duration
        while time.time() < end_time:
            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            
            self.cpu_samples.append(cpu_percent)
            self.memory_samples.append(memory_info.percent)
            
            logger.info(f"CPU: {cpu_percent}%, Memory: {memory_info.percent}%")
            
            # Check API responsiveness during monitoring
            self.get_system_status()
            
            time.sleep(interval)
        
        # Calculate and display stats
        avg_cpu = sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0
        max_cpu = max(self.cpu_samples) if self.cpu_samples else 0
        avg_mem = sum(self.memory_samples) / len(self.memory_samples) if self.memory_samples else 0
        max_mem = max(self.memory_samples) if self.memory_samples else 0
        avg_response = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        max_response = max(self.response_times) if self.response_times else 0
        
        logger.info(f"Resource monitoring complete:")
        logger.info(f"Average CPU: {avg_cpu:.1f}%, Max CPU: {max_cpu:.1f}%")
        logger.info(f"Average Memory: {avg_mem:.1f}%, Max Memory: {max_mem:.1f}%")
        logger.info(f"Average API Response: {avg_response:.3f}s, Max: {max_response:.3f}s")
        
        return {
            "avg_cpu": avg_cpu,
            "max_cpu": max_cpu, 
            "avg_memory": avg_mem,
            "max_memory": max_mem,
            "avg_response": avg_response,
            "max_response": max_response
        }
    
    def check_concurrent_operation(self):
        """Test concurrent operation of video streaming and detection"""
        logger.info("Testing concurrent operation...")
        
        # Enable detection
        self.toggle_detection(True)
        
        # Set up API polling in a separate thread
        stop_event = threading.Event()
        response_times = []
        
        def poll_api():
            while not stop_event.is_set():
                try:
                    start = time.time()
                    response = requests.get(f"{self.api_url}/status")
                    elapsed = time.time() - start
                    if response.status_code == 200:
                        response_times.append(elapsed)
                    time.sleep(0.2)  # Poll at 5 Hz
                except Exception as e:
                    logger.error(f"Error polling API: {e}")
        
        # Start API polling thread
        poll_thread = threading.Thread(target=poll_api)
        poll_thread.daemon = True
        poll_thread.start()
        
        # Access video stream in parallel
        try:
            logger.info("Testing video stream access...")
            start = time.time()
            response = requests.get(f"{self.base_url}/video_feed", stream=True, timeout=2)
            
            # Read a few frames to test streaming
            frame_count = 0
            for chunk in response.iter_content(chunk_size=10*1024):
                frame_count += chunk.count(b'--frame')
                if frame_count >= 5 or time.time() - start > 5:
                    break
            
            logger.info(f"Read {frame_count} frames from video stream")
        except requests.exceptions.ReadTimeout:
            logger.info("Video stream timeout after receiving some frames (expected)")
        except Exception as e:
            logger.error(f"Error accessing video stream: {e}")
        
        # Stop API polling
        stop_event.set()
        poll_thread.join(timeout=1)
        
        # Calculate response time stats
        if response_times:
            avg_time = sum(response_times) / len(response_times)
            max_time = max(response_times)
            logger.info(f"API responsiveness during video streaming:")
            logger.info(f"Average response time: {avg_time:.3f}s, Max: {max_time:.3f}s")
            
            if avg_time > 0.5:
                logger.warning("API response times seem high - possible concurrency issue")
            else:
                logger.info("API response times good - concurrent operation seems effective")
        
        # Test resource usage during concurrent operation
        logger.info("Monitoring resources during concurrent operation...")
        return self.monitor_resources(duration=10, interval=1.0)
    
    def run_detection_toggle_tests(self):
        """Test toggling detection on and off"""
        logger.info("Starting detection toggle tests...")
        
        # Get initial status
        initial_status = self.get_system_status()
        initial_active = initial_status.get("detection_active", False) if initial_status else False
        
        # Test disabling detection
        logger.info("Testing detection disable...")
        self.toggle_detection(False)
        time.sleep(2)
        status = self.get_system_status()
        if status and status.get("detection_active") == False:
            logger.info("Detection disabled successfully")
        else:
            logger.error("Failed to disable detection")
        
        # Monitor resources with detection off
        logger.info("Monitoring resources with detection disabled...")
        resources_off = self.monitor_resources(duration=5, interval=1.0)
        
        # Test enabling detection
        logger.info("Testing detection enable...")
        self.toggle_detection(True)
        time.sleep(2)
        status = self.get_system_status()
        if status and status.get("detection_active") == True:
            logger.info("Detection enabled successfully")
        else:
            logger.error("Failed to enable detection")
        
        # Monitor resources with detection on
        logger.info("Monitoring resources with detection enabled...")
        resources_on = self.monitor_resources(duration=5, interval=1.0)
        
        # Rapid toggle test
        logger.info("Testing rapid detection toggle...")
        for i in range(3):
            self.toggle_detection(False)
            time.sleep(0.5)
            self.toggle_detection(True)
            time.sleep(0.5)
        
        # Get final status
        time.sleep(1)
        final_status = self.get_system_status()
        final_active = final_status.get("detection_active", False) if final_status else False
        
        logger.info(f"Toggle tests complete. Final detection state: {'Active' if final_active else 'Inactive'}")
        
        # Return to initial state if needed
        if initial_active != final_active:
            logger.info(f"Returning to initial detection state: {'Active' if initial_active else 'Inactive'}")
            self.toggle_detection(initial_active)
        
        # Compare resource usage
        logger.info("Resource usage comparison (Detection Off vs On):")
        logger.info(f"CPU: {resources_off['avg_cpu']:.1f}% vs {resources_on['avg_cpu']:.1f}%")
        logger.info(f"Memory: {resources_off['avg_memory']:.1f}% vs {resources_on['avg_memory']:.1f}%")
        logger.info(f"API Response: {resources_off['avg_response']:.3f}s vs {resources_on['avg_response']:.3f}s")
        
        return {
            "off": resources_off,
            "on": resources_on
        }
    
    def run_database_verification(self):
        """Verify database is logging detection events"""
        logger.info("Running database verification...")
        
        # Query different event types
        events_start = self.query_database("detection_start", 5)
        events_end = self.query_database("detection_end", 5)
        events_direction = self.query_database("direction", 5)
        
        # Get most recent events
        all_events = self.query_database(limit=10)
        
        return {
            "detection_start": len(events_start),
            "detection_end": len(events_end),
            "direction": len(events_direction),
            "all_events": len(all_events)
        }
    
    def run_complete_test_suite(self):
        """Run the complete test suite"""
        logger.info("Starting ZVision complete test suite...")
        
        # 1. Check initial system status
        logger.info("1. Checking initial system status...")
        initial_status = self.get_system_status()
        
        # 2. Check metrics
        logger.info("2. Checking metrics...")
        metrics = self.get_recent_metrics()
        
        # 3. Test concurrent operation
        logger.info("3. Testing concurrent operation...")
        concurrency_results = self.check_concurrent_operation()
        
        # 4. Test detection toggling
        logger.info("4. Testing detection toggling...")
        toggle_results = self.run_detection_toggle_tests()
        
        # 5. Verify database
        logger.info("5. Verifying database...")
        db_results = self.run_database_verification()
        
        # 6. Check recent detections
        logger.info("6. Checking recent detections...")
        recent = self.get_recent_detections()
        
        # 7. Final resource check
        logger.info("7. Final resource check...")
        final_resources = self.monitor_resources(duration=5, interval=1.0)
        
        # 8. Final status check
        logger.info("8. Final status check...")
        final_status = self.get_system_status()
        
        # Output summary
        logger.info("\n" + "="*50)
        logger.info("TEST SUMMARY")
        logger.info("="*50)
        
        logger.info(f"System Status: {'OK' if initial_status and final_status else 'ISSUE'}")
        logger.info(f"Metrics Access: {'OK' if metrics else 'ISSUE'}")
        logger.info(f"Detection Toggle: {'OK' if toggle_results else 'ISSUE'}")
        logger.info(f"Database Logging: {'OK' if sum(db_results.values()) > 0 else 'ISSUE'}")
        logger.info(f"Recent Detections: {'OK' if recent else 'ISSUE'}")
        
        cpu_ok = final_resources["max_cpu"] < 90  # Arbitrary threshold
        memory_ok = final_resources["max_memory"] < 90  # Arbitrary threshold
        response_ok = final_resources["max_response"] < 1.0  # 1 second threshold
        
        logger.info(f"CPU Usage: {'OK' if cpu_ok else 'HIGH'} ({final_resources['max_cpu']:.1f}%)")
        logger.info(f"Memory Usage: {'OK' if memory_ok else 'HIGH'} ({final_resources['max_memory']:.1f}%)")
        logger.info(f"API Response: {'OK' if response_ok else 'SLOW'} ({final_resources['max_response']:.3f}s)")
        
        overall = all([
            initial_status and final_status,
            metrics,
            toggle_results,
            sum(db_results.values()) > 0,
            recent,
            cpu_ok,
            memory_ok,
            response_ok
        ])
        
        logger.info(f"\nOVERALL RESULT: {'PASS' if overall else 'ISSUES DETECTED'}")
        logger.info("="*50)
        
        return {
            "overall": overall,
            "status": initial_status and final_status,
            "metrics": bool(metrics),
            "toggle": bool(toggle_results),
            "database": sum(db_results.values()) > 0,
            "detections": bool(recent),
            "resources": {
                "cpu_ok": cpu_ok,
                "memory_ok": memory_ok,
                "response_ok": response_ok
            }
        }

def main():
    parser = argparse.ArgumentParser(description="ZVision Performance and Concurrency Test")
    parser.add_argument("--host", default="localhost", help="ZVision server host")
    parser.add_argument("--port", default=5000, type=int, help="ZVision server port")
    parser.add_argument("--test", choices=["all", "status", "concurrency", "toggle", "database", "resources"], 
                       default="all", help="Test to run")
    args = parser.parse_args()
    
    tester = ZVisionTester(host=args.host, port=args.port)
    
    if args.test == "all":
        tester.run_complete_test_suite()
    elif args.test == "status":
        tester.get_system_status()
        tester.get_recent_metrics()
        tester.get_recent_detections()
    elif args.test == "concurrency":
        tester.check_concurrent_operation()
    elif args.test == "toggle":
        tester.run_detection_toggle_tests()
    elif args.test == "database":
        tester.run_database_verification()
    elif args.test == "resources":
        tester.monitor_resources(duration=30, interval=1.0)

if __name__ == "__main__":
    main() 