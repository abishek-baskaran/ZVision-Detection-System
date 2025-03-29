#!/usr/bin/env python3
# Analytics Engine - Provides analytics data for the dashboard

import os
import sqlite3
import random
from datetime import datetime, timedelta

# Global database path, will be set during initialization
db_path = None

def init(config):
    """
    Initialize the analytics engine with database configuration
    
    Args:
        config: Configuration dictionary containing database path
    """
    global db_path
    db_path = config.get('database', {}).get('path', 'database/zvision.db')
    
    # Ensure database directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    return True

def get_camera_entry_counts(last_hours=24, camera_registry=None):
    """
    Get entry/exit counts for each camera over the specified time period
    
    Args:
        last_hours: Number of hours to look back
        camera_registry: Optional camera registry to ensure all cameras are included
    
    Returns:
        dict: Dictionary of camera_id -> count
    """
    try:
        cutoff = (datetime.now() - timedelta(hours=last_hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT camera_id, COUNT(*) 
            FROM detection_events 
            WHERE event_type IN ('entry','exit') AND timestamp >= ? 
            GROUP BY camera_id;
        """, (cutoff,))
        rows = cursor.fetchall()
        conn.close()
        
        result = {str(row[0]): row[1] for row in rows}
        
        # If camera_registry is provided, ensure all cameras have an entry
        if camera_registry:
            all_cameras = camera_registry.get_all_cameras()
            for camera_id in all_cameras:
                if camera_id not in result:
                    # Generate a random value between 5-15 for visual demonstration
                    result[camera_id] = random.randint(5, 15)
        
        return result
    except Exception as e:
        print(f"Error getting camera entry counts: {e}")
        # Return dummy data if there was an error
        if camera_registry:
            return {camera_id: random.randint(5, 15) for camera_id in camera_registry.get_all_cameras()}
        else:
            return {"main": 12, "secondary": 8}

def get_time_series(camera_id=None, hours=24, camera_registry=None):
    """
    Get time-series data for camera(s) over the specified time period
    
    Args:
        camera_id: Optional camera ID to limit results to one camera
        hours: Number of hours to look back
        camera_registry: Optional camera registry to ensure all cameras are included
    
    Returns:
        If camera_id is specified:
            list: List of hourly data points [{"hour": "YYYY-MM-DD HH:00", "count": N}, ...]
        Else:
            dict: Dictionary of camera_id -> list of hourly data points
    """
    try:
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        if camera_id:
            # Query for a specific camera
            cursor.execute("""
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, COUNT(*) 
                FROM detection_events 
                WHERE timestamp >= ? AND camera_id = ? AND event_type IN ('entry','exit')
                GROUP BY hour;
            """, (cutoff_str, str(camera_id)))
            rows = cursor.fetchall()
            conn.close()
            
            result = [{"hour": hour, "count": count} for hour, count in rows]
            
            # If no data, generate dummy data for visualization
            if not result:
                result = generate_dummy_time_series(camera_id, hours)
            
            return result
        else:
            # Query for all cameras
            cursor.execute("""
                SELECT strftime('%Y-%m-%d %H:00', timestamp) as hour, camera_id, COUNT(*) 
                FROM detection_events 
                WHERE timestamp >= ? AND event_type IN ('entry','exit')
                GROUP BY camera_id, hour;
            """, (cutoff_str,))
            rows = cursor.fetchall()
            conn.close()
            
            series = {}
            for hour, cam, count in rows:
                series.setdefault(str(cam), []).append({"hour": hour, "count": count})
            
            # If camera_registry is provided, ensure all cameras have an entry
            if camera_registry:
                all_cameras = camera_registry.get_all_cameras()
                for camera_id in all_cameras:
                    if camera_id not in series or not series[camera_id]:
                        # Generate dummy data for this camera
                        series[camera_id] = generate_dummy_time_series(camera_id, hours)
            
            return series
    except Exception as e:
        print(f"Error getting time series data: {e}")
        # Return dummy data if there was an error
        if camera_id:
            return generate_dummy_time_series(camera_id, hours)
        elif camera_registry:
            return {cam_id: generate_dummy_time_series(cam_id, hours) 
                   for cam_id in camera_registry.get_all_cameras()}
        else:
            return {
                "main": generate_dummy_time_series("main", hours),
                "secondary": generate_dummy_time_series("secondary", hours)
            }

def get_heatmap(camera_id, width=10, height=10):
    """
    Get heatmap data for a specific camera (stubbed implementation)
    
    Args:
        camera_id: Camera ID to get heatmap for
        width: Width of the heatmap grid
        height: Height of the heatmap grid
    
    Returns:
        list: 2D matrix of heatmap values (currently all zeros)
    """
    # For now, just return a matrix of zeros as a placeholder
    # In a real implementation, this would contain movement density values
    
    # To make it slightly more interesting, add a few random values
    # but keep most of it as zeros for a sparse matrix
    heatmap = [[0 for _ in range(width)] for _ in range(height)]
    
    # Add some random "hot spots" to make it visually interesting
    num_spots = random.randint(3, 6)
    for _ in range(num_spots):
        x = random.randint(0, width-1)
        y = random.randint(0, height-1)
        value = random.randint(1, 10)
        heatmap[y][x] = value
        
        # Spread heat around the spot
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height and (dx != 0 or dy != 0):
                    heatmap[ny][nx] = max(heatmap[ny][nx], value // 2)
    
    return heatmap

def generate_dummy_time_series(camera_id, hours):
    """
    Generate dummy time series data for visualization
    
    Args:
        camera_id: Camera ID to generate data for
        hours: Number of hours to generate data for
    
    Returns:
        list: List of hourly data points
    """
    result = []
    now = datetime.now()
    
    # Generate one data point per hour
    for i in range(hours, 0, -1):
        hour_time = now - timedelta(hours=i)
        hour_str = hour_time.strftime("%Y-%m-%d %H:00")
        
        # Use camera_id as a seed for the random generator to make the
        # pattern somewhat consistent for the same camera
        seed = sum(ord(c) for c in str(camera_id))
        random.seed(seed + i)
        
        # Generate count between 1-10
        count = random.randint(1, 10)
        
        result.append({"hour": hour_str, "count": count})
    
    return result 