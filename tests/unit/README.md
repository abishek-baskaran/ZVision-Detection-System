# Unit Tests

This directory contains unit tests for the ZVision detection system components.

## Test Files

- **test_roi_api.py**: Tests for the ROI configuration API endpoints
- **test_analytics_engine.py**: Tests for the analytics engine functionality
- **test_snapshot_capture.py**: Tests for the snapshot capture functionality
- **test_storage_manager.py**: Tests for the snapshot storage manager
- **test_snapshot_api.py**: Tests for the snapshot API endpoints
- **test_integration_snapshot.py**: Integration tests for the snapshot workflow
- **test_camera_manager.py**: Tests for camera connection reliability features
- **test_multi_camera_detection.py**: Tests for multi-camera detection functionality

## Running the Tests

To run all unit tests:

```bash
# Run from project root
python -m unittest discover tests/unit
```

To run a specific test file:

```bash
# Run from project root
python -m unittest tests/unit/test_roi_api.py
python -m unittest tests/unit/test_analytics_engine.py
python -m unittest tests/unit/test_snapshot_capture.py
python -m unittest tests/unit/test_camera_manager.py
```

## ROI API Tests

The `test_roi_api.py` file tests the following functionality:

- Setting ROI coordinates and entry direction
- Clearing ROI configuration
- Verifying ROI information is included in the status endpoint

These tests use mock objects to simulate dependencies, allowing for isolated testing of the API functionality without requiring a live camera or detection model.

## Analytics Engine Tests

The `test_analytics_engine.py` file tests the following functionality:

- Camera entry/exit count aggregation 
- Time-series data generation for different time periods
- Camera-specific time-series filtering
- Heatmap data generation
- Integration with camera registry and database

These tests verify both the backend analytics calculations and the proper API response formatting, ensuring that the analytics system provides accurate and useful data for multi-camera deployments.

## Snapshot Capture Tests

The `test_snapshot_capture.py` file tests the following functionality:

- Snapshot capture on person detection
- Continuous snapshot capture during detections
- Final snapshot capture when a person leaves the frame
- Proper file naming and directory structure
- Database logging of snapshot events
- Camera-specific snapshot organization

## Storage Manager Tests

The `test_storage_manager.py` file tests the following functionality:

- FIFO (First-In-First-Out) snapshot cleanup
- Camera-specific storage management
- Maximum file count enforcement
- Directory creation and management
- Error handling for missing directories

## Snapshot API Tests

The `test_snapshot_api.py` file tests the following functionality:

- Retrieving recent snapshots for a specific camera
- Limiting the number of returned snapshots
- API endpoint for fetching a specific snapshot image
- Error handling for invalid camera IDs or snapshot paths

## Camera Manager Tests

The `test_camera_manager.py` file tests the following functionality:

- Camera initialization for different source types (USB, IP, video files)
- Warm-up period implementation for USB cameras
- Consecutive failure tracking and reconnection
- Thread management and cleanup
- Video file looping and frame rate control
- Error handling during camera initialization and operation

## Test Coverage

The unit tests aim to verify:

1. Correct API response codes
2. Proper JSON response structures
3. Integration with the detection manager and analytics engine
4. Error handling for invalid inputs
5. Data formatting and aggregation logic
6. Snapshot capture and storage functionality
7. Camera reliability and recovery features

## Dependencies

To run the unit tests, you need:

- Python unittest framework (built-in)
- Mock library for Python

Install with:

```bash
pip install mock
```

## Adding New Tests

When adding new tests:

1. Follow the existing pattern of test classes and methods
2. Use descriptive test method names (`test_feature_behavior_context`)
3. Include docstrings explaining the purpose of each test
4. Use assert methods from unittest for verification
5. Mock external dependencies when appropriate 