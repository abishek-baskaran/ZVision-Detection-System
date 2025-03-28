# Manual Testing Tools

This directory contains tools and guides for manually testing the ZVision detection system.

## Test Scripts

- **test_roi_persistence.py**: Tests ROI persistence functionality and database integration
- **test_roi_html_interface.py**: Tests the HTML interface for drawing and configuring ROI

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

## Troubleshooting

If tests fail:
- Check the server logs for errors
- Verify the database connection is working
- Ensure the web server is running properly
- Check browser console for any JavaScript errors 