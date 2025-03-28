#!/usr/bin/env python3
# Test script to verify ROI persistence functionality

import sys
import os
import time
import random
import requests
import json
import sqlite3

# Add the parent directory to the path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from managers.resource_provider import ResourceProvider
from managers.database_manager import DatabaseManager

def get_db_path():
    """Get the database path from config"""
    resource_provider = ResourceProvider("config.yaml")
    config = resource_provider.get_config()
    return config.get('database', {}).get('path', 'database/zvision.db')

def check_camera_config_table():
    """Check if the camera_config table exists in the database"""
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='camera_config';")
        result = cursor.fetchone()
        
        if result:
            print("✅ camera_config table exists in the database")
            
            # Check table structure
            cursor.execute("PRAGMA table_info(camera_config);")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            expected_columns = ['camera_id', 'roi_x1', 'roi_y1', 'roi_x2', 'roi_y2', 'entry_direction']
            missing_columns = [col for col in expected_columns if col not in column_names]
            
            if not missing_columns:
                print("✅ camera_config table has all required columns")
            else:
                print(f"❌ camera_config table is missing columns: {missing_columns}")
        else:
            print("❌ camera_config table does not exist in the database")
        
        conn.close()
        return result is not None
        
    except Exception as e:
        print(f"Error checking camera_config table: {e}")
        return False

def check_api_roi_endpoints():
    """Test the ROI API endpoints"""
    base_url = "http://localhost:5000"
    
    try:
        # Check status endpoint
        response = requests.get(f"{base_url}/api/status")
        if response.status_code == 200:
            status_data = response.json()
            if 'roi' in status_data:
                print("✅ Status endpoint includes ROI information")
            else:
                print("❌ Status endpoint is missing ROI information")
        else:
            print(f"❌ Error accessing status endpoint: {response.status_code}")
        
        # Generate random ROI
        x1 = random.randint(50, 150)
        y1 = random.randint(50, 150)
        x2 = random.randint(x1 + 100, x1 + 300)
        y2 = random.randint(y1 + 100, y1 + 300)
        entry_direction = random.choice(["LTR", "RTL"])
        
        print(f"Setting ROI to: ({x1}, {y1}, {x2}, {y2}) with entry direction: {entry_direction}")
        
        # Set ROI
        roi_data = {
            "x1": x1,
            "y1": y1,
            "x2": x2,
            "y2": y2,
            "entry_direction": entry_direction
        }
        
        response = requests.post(
            f"{base_url}/api/cameras/0/roi", 
            json=roi_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ ROI set successfully")
        else:
            print(f"❌ Failed to set ROI: {response.status_code} - {response.text}")
            return False
        
        # Verify ROI was saved to the database
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM camera_config WHERE camera_id = '0';")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            print(f"✅ ROI was saved to the database: {row}")
        else:
            print("❌ ROI was not saved to the database")
            return False
        
        # Check if the ROI is returned in the status
        response = requests.get(f"{base_url}/api/status")
        if response.status_code == 200:
            status_data = response.json()
            if 'roi' in status_data and status_data['roi'].get('coords'):
                roi_coords = status_data['roi']['coords']
                if (roi_coords['x1'] == x1 and roi_coords['y1'] == y1 and 
                    roi_coords['x2'] == x2 and roi_coords['y2'] == y2 and
                    status_data['roi']['entry_direction'] == entry_direction):
                    print("✅ ROI is correctly returned in the status endpoint")
                else:
                    print(f"❌ ROI in status doesn't match what was set: {roi_coords}")
                    return False
            else:
                print("❌ ROI information missing from status endpoint")
                return False
        else:
            print(f"❌ Error accessing status endpoint: {response.status_code}")
            return False
        
        # Now clear the ROI
        response = requests.post(f"{base_url}/api/cameras/0/roi/clear")
        if response.status_code == 200:
            print("✅ ROI cleared successfully")
        else:
            print(f"❌ Failed to clear ROI: {response.status_code} - {response.text}")
            return False
        
        # Verify ROI was removed from the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM camera_config WHERE camera_id = '0';")
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print("✅ ROI was removed from the database")
        else:
            print(f"❌ ROI was not removed from the database: {row}")
            return False
        
        # Check if the ROI is no longer in the status
        response = requests.get(f"{base_url}/api/status")
        if response.status_code == 200:
            status_data = response.json()
            if 'roi' in status_data and not status_data['roi'].get('coords'):
                print("✅ ROI is correctly shown as cleared in the status endpoint")
            else:
                print(f"❌ ROI still appears in status after clearing: {status_data.get('roi')}")
                return False
        else:
            print(f"❌ Error accessing status endpoint: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"Error testing ROI API endpoints: {e}")
        return False

def main():
    print("\n=== Testing ROI Persistence ===\n")
    
    # Check if camera_config table exists
    if not check_camera_config_table():
        print("\n❌ camera_config table test failed. Cannot proceed with API tests.")
        return
    
    print("\n--- Testing ROI API Endpoints ---\n")
    if check_api_roi_endpoints():
        print("\n✅ All ROI persistence tests passed!")
    else:
        print("\n❌ Some ROI persistence tests failed.")

if __name__ == "__main__":
    main() 