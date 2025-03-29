#!/usr/bin/env python3
# Test script for multi-camera detection performance

import sys
import os
import time
import threading
import cv2
import psutil
import argparse
from collections import deque
import matplotlib.pyplot as plt
import numpy as np

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from managers.resource_provider import ResourceProvider
from managers.camera_registry import CameraRegistry
from managers.detection_manager import DetectionManager
from managers.dashboard_manager import DashboardManager
from managers.database_manager import DatabaseManager

def print_separator():
    """Print a separator line"""
    print('-' * 80)

def run_performance_test(num_cameras=2, duration=30, show_video=False):
    """
    Run a performance test with multiple cameras
    
    Args:
        num_cameras: Number of cameras to use
        duration: Duration in seconds
        show_video: Whether to show the video frames
    """
    print_separator()
    print(f"Starting multi-camera performance test with {num_cameras} cameras for {duration} seconds")
    print_separator()
    
    # Initialize resource provider
    resource_provider = ResourceProvider()
    logger = resource_provider.get_logger()
    
    # Create a camera registry
    camera_registry = CameraRegistry(resource_provider)
    
    # Create a dashboard manager
    dashboard_manager = DashboardManager(resource_provider)
    
    # Create a database manager
    db_manager = DatabaseManager(resource_provider)
    
    # Create a detection manager
    detection_manager = DetectionManager(resource_provider, camera_registry, dashboard_manager, db_manager)
    
    # Start all cameras
    camera_registry.start_all_cameras()
    
    # Give cameras time to initialize
    time.sleep(2)
    
    # Track resource usage
    cpu_history = deque(maxlen=100)
    memory_history = deque(maxlen=100)
    
    # Start resource monitoring thread
    stop_monitoring = threading.Event()
    
    def monitor_resources():
        while not stop_monitoring.is_set():
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory_percent = psutil.virtual_memory().percent
            
            cpu_history.append(cpu_percent)
            memory_history.append(memory_percent)
            
            print(f"CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%", end='\r')
    
    monitor_thread = threading.Thread(target=monitor_resources)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # Start video display thread if requested
    stop_display = threading.Event()
    
    if show_video:
        def display_frames():
            while not stop_display.is_set():
                cameras = camera_registry.get_active_cameras()
                
                for camera_id, camera in cameras.items():
                    frame = camera.get_latest_frame()
                    if frame is not None:
                        cv2.imshow(f"Camera {camera_id}", frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                time.sleep(0.03)  # ~30 FPS display
        
        display_thread = threading.Thread(target=display_frames)
        display_thread.daemon = True
        display_thread.start()
    
    # Start detection
    print("Starting multi-camera detection")
    detection_manager.start_all()
    
    # Wait for the specified duration
    print(f"Running for {duration} seconds...")
    time.sleep(duration)
    
    # Stop detection
    detection_manager.stop_all()
    
    # Stop monitoring and display
    stop_monitoring.set()
    stop_display.set()
    monitor_thread.join(timeout=1.0)
    
    if show_video:
        cv2.destroyAllWindows()
    
    # Print statistics
    print("\n")
    print_separator()
    print("Performance Test Results:")
    print_separator()
    
    # CPU statistics
    avg_cpu = sum(cpu_history) / len(cpu_history) if cpu_history else 0
    max_cpu = max(cpu_history) if cpu_history else 0
    min_cpu = min(cpu_history) if cpu_history else 0
    
    print(f"CPU Usage: Avg: {avg_cpu:.1f}%, Max: {max_cpu:.1f}%, Min: {min_cpu:.1f}%")
    
    # Memory statistics
    avg_memory = sum(memory_history) / len(memory_history) if memory_history else 0
    max_memory = max(memory_history) if memory_history else 0
    min_memory = min(memory_history) if memory_history else 0
    
    print(f"Memory Usage: Avg: {avg_memory:.1f}%, Max: {max_memory:.1f}%, Min: {min_memory:.1f}%")
    
    # Detection statistics
    active_cameras = detection_manager.get_active_cameras()
    print(f"Active detection cameras: {len(active_cameras)}")
    
    # Resource statistics from detection manager
    resources = detection_manager.get_system_resources()
    print(f"Detection manager tracked avg CPU: {resources['avg_cpu']:.1f}%")
    print(f"Detection manager tracked avg Memory: {resources['avg_memory']:.1f}%")
    
    # Plot results
    plt.figure(figsize=(12, 6))
    
    # CPU plot
    plt.subplot(1, 2, 1)
    plt.plot(cpu_history)
    plt.title('CPU Usage')
    plt.xlabel('Time (0.5s intervals)')
    plt.ylabel('CPU %')
    plt.ylim(0, 100)
    plt.grid(True)
    
    # Memory plot
    plt.subplot(1, 2, 2)
    plt.plot(memory_history)
    plt.title('Memory Usage')
    plt.xlabel('Time (0.5s intervals)')
    plt.ylabel('Memory %')
    plt.ylim(0, 100)
    plt.grid(True)
    
    plt.tight_layout()
    
    # Save the plot
    plot_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'multi_camera_performance.png')
    plt.savefig(plot_file)
    print(f"Performance plot saved to: {plot_file}")
    
    # Check if we are likely to exceed system capacity
    feasibility = ""
    if avg_cpu > 90:
        feasibility = "NOT feasible - CPU usage too high"
    elif avg_memory > 90:
        feasibility = "NOT feasible - Memory usage too high"
    elif avg_cpu > 70:
        feasibility = "Barely feasible - CPU usage is high"
    elif avg_memory > 70:
        feasibility = "Barely feasible - Memory usage is high"
    else:
        feasibility = "Feasible - Resource usage is acceptable"
    
    print_separator()
    print(f"Feasibility assessment: {feasibility}")
    print_separator()
    
    # Clean up
    camera_registry.stop_all_cameras()
    
    return {
        "avg_cpu": avg_cpu,
        "max_cpu": max_cpu,
        "avg_memory": avg_memory,
        "max_memory": max_memory,
        "feasible": "NOT" not in feasibility
    }

def main():
    """
    Main function
    """
    parser = argparse.ArgumentParser(description='Test multi-camera detection performance')
    parser.add_argument('--cameras', type=int, default=2, help='Number of cameras to test')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    parser.add_argument('--show', action='store_true', help='Show video frames')
    
    args = parser.parse_args()
    
    # Run the test
    result = run_performance_test(args.cameras, args.duration, args.show)
    
    # Return exit code based on feasibility
    return 0 if result["feasible"] else 1

if __name__ == '__main__':
    sys.exit(main()) 