# Manual Testing Tools

This directory contains tools and guides for manually testing the ZVision detection system.

## Test Scripts

- **test_roi_persistence.py**: Tests ROI persistence functionality and database integration
- **test_roi_html_interface.py**: Tests the HTML interface for drawing and configuring ROI
- **test_analytics_endpoints.py**: Tests the analytics endpoints for multi-camera data
- **snapshot_test.py**: Tests the snapshot capture and storage functionality
- **camera_reliability_test.py**: Tests the camera connection reliability and recovery

## Running the Tests

### ROI Persistence Test

Tests the database storage and retrieval of ROI configuration:

```bash
# Run from project root
python tests/manual/test_roi_persistence.py
```

The test verifies:
- Creation of the camera_config table in the database
- API endpoints for setting and clearing ROI
- Persistence of ROI settings in the database
- Proper inclusion of ROI data in the status endpoint

### ROI HTML Interface Test

Tests the frontend interface for configuring ROI:

```bash
# Run from project root
python tests/manual/test_roi_html_interface.py
```

This test:
- Loads the dashboard page
- Tests canvas drawing functionality
- Tests saving and loading ROI configuration
- Verifies direction selection controls

### Analytics Endpoints Test

Tests the analytics API endpoints:

```bash
# Run from project root
python tests/manual/test_analytics_endpoints.py
```

This test:
- Verifies the compare endpoint for cross-camera metrics
- Tests time-series data for hourly detection trends
- Confirms heatmap data generation for movement visualization
- Checks camera-specific filtering functionality
- Validates time period parameter handling

### Snapshot Functionality Test

Tests the snapshot capture, storage, and retrieval functionality:

```bash
# Run from project root
python tests/manual/snapshot_test.py
```

This test:
- Creates test snapshots in a designated directory
- Verifies snapshot file creation and naming
- Tests database logging of snapshot paths
- Confirms FIFO storage management functionality
- Validates API endpoints for retrieving snapshots

### Camera Reliability Test

Tests the camera connection recovery and reliability features:

```bash
# Run from project root
python tests/manual/camera_reliability_test.py
```

This test:
- Simulates camera connection failures
- Verifies warm-up period functionality
- Tests consecutive failure handling and reconnection
- Confirms thread management and cleanup
- Validates video file handling and looping

## Manual Testing Checklist

To manually test the ROI functionality:

1. **Canvas Drawing**
   - Open the system dashboard
   - Verify you can draw a box on the video feed
   - Check that the box is properly displayed

2. **ROI Persistence**
   - Draw and save an ROI configuration
   - Restart the server
   - Verify the ROI is loaded and displayed correctly

3. **Direction Mapping**
   - Configure left-to-right as "entry"
   - Verify people moving left-to-right are counted as entries
   - Change to right-to-left as "entry" 
   - Verify people moving right-to-left are now counted as entries

4. **Detection Behavior**
   - Verify detection only occurs within the configured ROI
   - Verify people outside the ROI are not counted
   - Reset the ROI and verify detection returns to full-frame

To manually test the Analytics functionality:

1. **Compare Endpoint**
   - Access `/api/analytics/compare` via browser or curl
   - Verify that metrics for all cameras are included
   - Check that totals are calculated correctly
   - Test with different time period parameters

2. **Time Series Endpoint**
   - Access `/api/analytics/time-series` for all cameras
   - Test camera-specific filtering with the camera parameter
   - Verify hourly data points are provided in chronological order
   - Check that data points include both hour and count values

3. **Heatmap Endpoint**
   - Access `/api/analytics/heatmap?camera=main`
   - Verify the heatmap dimensions match the requested width/height
   - Check that the data format is a 2D matrix of numeric values
   - Test with different width/height parameters

To manually test the Snapshot functionality:

1. **Snapshot Capture**
   - Walk in front of the camera to trigger a detection
   - Verify snapshots are saved in the correct camera-specific folder
   - Confirm that multiple snapshots are taken during the detection
   - Check that a final snapshot is taken when exiting the frame

2. **FIFO Storage Management**
   - Create many snapshots by repeatedly triggering detections
   - Verify that older snapshots are deleted when the limit is reached
   - Check that the snapshot count stays at or below the configured maximum

3. **API Retrieval**
   - Access `/api/snapshots/<camera_id>` to list recent snapshots
   - Verify the snapshot timestamp and metadata
   - Access individual snapshots using the `/api/snapshot/<path>` endpoint
   - Check that snapshots are correctly displayed in the browser

To manually test Camera Reliability:

1. **Connection Recovery**
   - Temporarily disconnect the USB webcam during operation
   - Reconnect the webcam and verify it automatically recovers
   - Check logs for warm-up period and reconnection messages
   
2. **Video File Handling**
   - Configure a video file as a camera source
   - Verify looping functionality when the video ends
   - Confirm proper frame rate control during playback

3. **Error Handling**
   - Monitor logs during camera failures
   - Verify appropriate error messages
   - Confirm that the UI shows camera status correctly

## Troubleshooting

If tests fail:
- Check the server logs for errors
- Verify the database connection is working
- Ensure the web server is running properly
- Check browser console for any JavaScript errors
- Verify the camera is properly connected and permissions are set correctly
- Check that snapshot directories exist and are writable 