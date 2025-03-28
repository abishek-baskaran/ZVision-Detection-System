#!/usr/bin/env python3
# Manual Test Script for ROI HTML Interface
# Run with: python tests/manual/test_roi_html_interface.py

import sys
import os
import time
import json
import requests
import unittest
from urllib.parse import urljoin

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class TestROIHTMLInterface(unittest.TestCase):
    """
    Manual test cases for the ROI HTML Interface.
    """
    
    def setUp(self):
        """Set up the test environment"""
        self.base_url = "http://localhost:5000"
        self.test_roi = {
            "x1": 100, 
            "y1": 100, 
            "x2": 300, 
            "y2": 300, 
            "entry_direction": "LTR"
        }
    
    def test_01_verify_interface_loaded(self):
        """Verify that the ROI interface HTML elements are loaded"""
        print("\n1. Verifying ROI HTML Interface Elements...")
        try:
            response = requests.get(self.base_url)
            self.assertEqual(response.status_code, 200, "Failed to load dashboard page")
            
            # Check for expected HTML elements
            expected_elements = [
                'id="roi-canvas"',
                'id="roi-controls"',
                'id="save-roi"',
                'id="reset-roi"',
                'name="entryDir" value="LTR"',
                'name="entryDir" value="RTL"'
            ]
            
            for element in expected_elements:
                self.assertIn(element, response.text, f"Missing HTML element: {element}")
            
            print("✓ ROI HTML Interface elements verified")
            return True
        except Exception as e:
            print(f"✗ Error verifying interface: {e}")
            return False
    
    def test_02_set_roi_via_api(self):
        """Test setting ROI via API endpoint"""
        print("\n2. Testing ROI API Endpoint (POST)...")
        try:
            endpoint = urljoin(self.base_url, "/api/cameras/0/roi")
            response = requests.post(
                endpoint,
                json=self.test_roi,
                headers={"Content-Type": "application/json"}
            )
            
            self.assertEqual(response.status_code, 200, "Failed to set ROI")
            data = response.json()
            self.assertTrue(data.get("success"), "API returned success=false")
            
            print("✓ ROI successfully set via API")
            return True
        except Exception as e:
            print(f"✗ Error setting ROI: {e}")
            return False
    
    def test_03_verify_roi_in_status(self):
        """Verify ROI information is included in status response"""
        print("\n3. Verifying ROI in status endpoint...")
        try:
            endpoint = urljoin(self.base_url, "/api/status")
            response = requests.get(endpoint)
            
            self.assertEqual(response.status_code, 200, "Failed to get status")
            data = response.json()
            
            # Check if ROI information is in the response
            self.assertIn("roi", data, "ROI information missing from status")
            self.assertIn("coords", data["roi"], "ROI coordinates missing")
            self.assertIn("entry_direction", data["roi"], "Entry direction missing")
            
            # Verify ROI values match what we set
            coords = data["roi"]["coords"]
            self.assertEqual(coords["x1"], self.test_roi["x1"], "ROI x1 mismatch")
            self.assertEqual(coords["y1"], self.test_roi["y1"], "ROI y1 mismatch")
            self.assertEqual(coords["x2"], self.test_roi["x2"], "ROI x2 mismatch")
            self.assertEqual(coords["y2"], self.test_roi["y2"], "ROI y2 mismatch")
            self.assertEqual(data["roi"]["entry_direction"], self.test_roi["entry_direction"], "Entry direction mismatch")
            
            print("✓ ROI correctly included in status response")
            return True
        except Exception as e:
            print(f"✗ Error verifying ROI in status: {e}")
            return False
    
    def test_04_clear_roi_via_api(self):
        """Test clearing ROI via API endpoint"""
        print("\n4. Testing Clear ROI API Endpoint...")
        try:
            endpoint = urljoin(self.base_url, "/api/cameras/0/roi/clear")
            response = requests.post(endpoint)
            
            self.assertEqual(response.status_code, 200, "Failed to clear ROI")
            data = response.json()
            self.assertTrue(data.get("success"), "API returned success=false")
            
            # Verify ROI is cleared in status
            status_endpoint = urljoin(self.base_url, "/api/status")
            status_response = requests.get(status_endpoint)
            status_data = status_response.json()
            
            # ROI should be empty or have null coords
            if "roi" in status_data:
                self.assertTrue(
                    "coords" not in status_data["roi"] or status_data["roi"]["coords"] is None,
                    "ROI was not properly cleared"
                )
            
            print("✓ ROI successfully cleared via API")
            return True
        except Exception as e:
            print(f"✗ Error clearing ROI: {e}")
            return False
    
    def test_05_instructions(self):
        """Print instructions for manual testing of the UI"""
        print("\n5. Manual UI Testing Instructions:")
        print("=" * 50)
        print("Now please open a browser and navigate to http://localhost:5000")
        print("Perform the following manual tests:")
        print("1. Draw a rectangle on the video feed to define an ROI")
        print("2. Select 'Left-to-Right = Entry' or 'Right-to-Left = Entry'")
        print("3. Click 'Save ROI Configuration' and verify success notification")
        print("4. Refresh the page and verify the ROI is still drawn")
        print("5. Click 'Reset ROI' and verify the ROI disappears")
        print("6. Draw a new ROI, save it, and test if detection only triggers within the ROI")
        print("=" * 50)
        return True

def main():
    """Run the manual tests"""
    test = TestROIHTMLInterface()
    
    # Setup test environment
    test.setUp()
    
    # Run API tests
    tests = [
        test.test_01_verify_interface_loaded,
        test.test_02_set_roi_via_api,
        test.test_03_verify_roi_in_status,
        test.test_04_clear_roi_via_api,
        test.test_05_instructions
    ]
    
    results = []
    for test_func in tests:
        results.append(test_func())
    
    # Print summary
    print("\nTest Summary:")
    print(f"Total tests: {len(tests)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")
    
    if all(results):
        print("\nAll tests passed!")
        print("Now perform the manual tests to verify the UI functionality.")
    else:
        print("\nSome tests failed. Please check the output for details.")

if __name__ == "__main__":
    main() 