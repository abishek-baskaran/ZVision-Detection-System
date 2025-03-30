# ZVision Testing Tools

This directory contains tools for testing the ZVision detection system performance, concurrency, and functionality.

## Directory Structure

- `performance/`: Contains performance testing scripts
- `manual/`: Contains manual testing checklists and guides
- `scripts/`: Contains utility scripts for testing setup

## Overview

The testing tools help verify that the ZVision system performs correctly according to specifications, especially concerning:

1. Concurrent operation of camera stream and detection
2. Resource usage monitoring (CPU and memory)
3. API responsiveness under load
4. Detection and tracking functionality
5. Database logging verification
6. Multi-camera analytics functionality

## Test Components

- **performance/test_performance.py**: Automated script to test various aspects of the system
- **manual/test_checklist.md**: Manual test checklist for verifying functionality
- **manual/test_roi_persistence.py**: Test script for verifying ROI persistence functionality
- **unit/test_roi_api.py**: Unit tests for ROI API endpoints
- **unit/test_analytics_engine.py**: Unit tests for analytics engine functionality
- **scripts/install_test_dependencies.sh**: Script to install required dependencies

## Getting Started

### Install Dependencies

First, install the required dependencies:

```bash
# From the project root directory:
./tests/scripts/install_test_dependencies.sh
```

This will install Python packages needed for performance testing.

### Run Automated Tests

The test_performance.py script provides several testing options:

```bash
# Run all tests (from project root)
python tests/performance/test_performance.py

# Test only system status endpoints
python tests/performance/test_performance.py --test status

# Test concurrent operation
python tests/performance/test_performance.py --test concurrency

# Test detection toggling
python tests/performance/test_performance.py --test toggle

# Verify database logging
python tests/performance/test_performance.py --test database

# Monitor resource usage for 30 seconds
python tests/performance/test_performance.py --test resources
```

You can also specify a different host or port:

```bash
python tests/performance/test_performance.py --host 192.168.1.100 --port 5000
```

### ROI Feature Tests

To test the Region of Interest functionality:

```bash
# Unit tests for ROI API endpoints
python -m unittest tests/unit/test_roi_api.py

# Test ROI persistence functionality
python tests/manual/test_roi_persistence.py
```

The ROI persistence test verifies:
- Database schema for ROI configuration
- API endpoints for setting/clearing ROI
- Loading ROI settings on system startup
- Inclusion of ROI in status endpoint

### Analytics Engine Tests

To test the Analytics Engine functionality:

```bash
# Unit tests for analytics engine functionality
python -m unittest tests/unit/test_analytics_engine.py

# Test analytics API endpoints
curl -s http://localhost:5000/api/analytics/compare | python -m json.tool
curl -s http://localhost:5000/api/analytics/time-series | python -m json.tool
curl -s http://localhost:5000/api/analytics/heatmap?camera=main | python -m json.tool
```

The analytics engine tests verify:
- Retrieval of camera entry/exit counts
- Time series data generation for detection events
- Heatmap visualization data
- Proper integration with the database
- Correct response formatting for API endpoints

### Manual Testing

Use the `manual/test_checklist.md` file as a guide for manual testing. This checklist covers:

- Idle mode testing
- Person detection testing
- Movement direction testing
- Toggle functionality
- Concurrent operation testing
- WebSocket notifications
- UI responsiveness
- Analytics functionality verification
- Performance optimization suggestions

## Interpreting Results

### Automated Test Results

The test_performance.py script will output a summary report that includes:

- System status check
- Metrics access verification
- Detection toggle functionality
- Database logging confirmation
- API response times
- CPU and memory usage statistics

A PASS result indicates all tests completed successfully. If ISSUES DETECTED appears, check the logs for specific failures.

### Performance Optimization

If you encounter performance issues during testing:

1. Check CPU usage - if consistently above 90%, consider optimizations
2. Verify memory usage isn't growing over time (indicates potential leaks)
3. Check API response times - should be under 1 second for good UX
4. If video streaming isn't smooth, consider reducing resolution or FPS

## Advanced Testing

For more advanced testing scenarios:

- Use multiple browser tabs to simulate concurrent users
- Run the system for extended periods to verify stability
- Test with different lighting conditions
- Use tools like `htop` alongside testing to monitor system-wide resources

## Troubleshooting

If tests fail or performance is poor:

1. Check logs for errors or warnings
2. Verify camera is working properly
3. Ensure detection model loaded correctly
4. Check database is accessible and writable
5. Verify network configuration if testing remotely

# Snapshot Functionality Tests

Several test files have been added to test the snapshot functionality:

## Unit Tests

- **test_snapshot_capture.py**: Tests for the snapshot capture functionality in the DetectionManager, verifying that snapshots are correctly saved and logged in the database.
- **test_storage_manager.py**: Tests for the SnapshotStorageManager's FIFO cleanup functionality, ensuring that older snapshots are properly deleted when the storage limit is reached.
- **test_snapshot_api.py**: Tests for the snapshot API endpoints, verifying that snapshots can be retrieved correctly through the API.

## Integration Tests

- **test_integration_snapshot.py**: End-to-end tests of the snapshot workflow, including capture, database logging, and FIFO cleanup. This tests the complete snapshot functionality across multiple components.

## Running the Tests

To run the snapshot tests:

```bash
# Run all snapshot tests
python -m unittest tests/unit/test_snapshot_capture.py tests/unit/test_storage_manager.py tests/unit/test_snapshot_api.py tests/unit/test_integration_snapshot.py

# Run a specific test file
python -m unittest tests/unit/test_snapshot_capture.py
```

## Validation Criteria

The tests validate that:

1. Snapshots are correctly captured at the start and end of detections
2. Snapshots are properly deleted in FIFO manner when exceeding the storage limit
3. Snapshots are correctly logged in the database
4. Snapshot paths in the database correspond to actual files on disk
5. The snapshot API endpoints correctly retrieve and serve snapshot images 