# ZVision System Manual Test Checklist

This checklist helps verify the correct operation of the ZVision detection system according to requirements.

## Prerequisites

- ZVision server is running
- Camera is connected and operational
- Web browser is available to access the UI
- Python environment is set up for automated tests

## Functional Testing Scenarios

### 1. Idle Mode Testing

- [ ] **Start the system with no person in frame**
  - Dashboard should show "Person Detected: No"
  - Video streaming should be smooth
  - CPU usage should be low (check with `python tests/performance/test_performance.py --test resources`)
  - Metrics should not increase (footfall count remains stable)
  - Detection should be running at 1 FPS in idle mode (check logs)

### 2. Person Detection Testing

- [ ] **Person enters frame**
  - Within ~1 second the system should detect the person
  - Dashboard "Person Detected" should switch to "Yes" with green indicator
  - "Movement Direction" may initially show "unknown"
  - Footfall count should increment by 1 on first detection
  - Detection should process at ~5 FPS (check logs)
  - Video stream should remain smooth despite increased processing

### 3. Movement Direction Testing

- [ ] **Move across frame left-to-right**
  - System should log the direction
  - UI should update "Movement Direction" to "left_to_right"
  - Direction count in metrics should increment
  - Verify direction is captured only once per crossing

- [ ] **Move across frame right-to-left**
  - System should log the direction
  - UI should update "Movement Direction" to "right_to_left"
  - Direction count in metrics should increment
  - Verify direction is captured only once per crossing

### 4. Person Leaves Frame Testing

- [ ] **Person disappears from frame**
  - After 1-2 seconds, system should mark "Person Detected: No"
  - System should switch back to idle mode ("switching to idle mode" in logs)
  - Footfall count should remain the same (doesn't increment on disappearance)
  - Detection thread should return to 1 FPS after a few seconds

### 5. Detection Toggle Testing

- [ ] **Toggle detection off**
  - With no one in frame, press "Pause Detection"
  - Status should indicate detection is off
  - Detection thread should stop (check logs or CPU drop)
  - Video stream should continue unaffected
  - When walking in front of camera, "Person Detected" remains "No"

- [ ] **Toggle detection on**
  - Press "Resume Detection"
  - Detection thread should restart
  - System should quickly detect person if in frame
  - Footfall count should increment (new detection event after pause)

- [ ] **Rapid toggle testing**
  - Toggle detection on/off quickly several times
  - System should handle this without crashes
  - Final state should match what's shown in UI

### 6. Concurrent Operation Testing

- [ ] **Video streaming during detection**
  - With person in frame and detection active, video should remain smooth
  - API endpoints should remain responsive
  - Run `python tests/performance/test_performance.py --test concurrency` to verify

- [ ] **High load testing**
  - Multiple people moving in frame
  - API endpoints should still respond quickly
  - System should track multiple entries/exits correctly

### 7. Resource Usage Testing

- [ ] **Monitor CPU and memory**
  - Run `python tests/performance/test_performance.py --test resources` during different scenarios
  - CPU should remain under 90% to avoid thermal throttling
  - Memory usage should be stable (no leaks)
  - If CPU is consistently near 100%, consider reducing resolution/FPS

### 8. Database Verification

- [ ] **Check event logging**
  - Run `python tests/performance/test_performance.py --test database`
  - Verify entries in detection_events for:
    - detection_start events
    - detection_end events
    - direction events
  - Database entries should match what's shown in UI

## WebSocket Notification Testing

- [ ] **Open test page**
  - Navigate to test page at http://localhost:5000/
  - Verify WebSocket connection is established

- [ ] **Receive real-time events**
  - When person is detected, WebSocket should emit 'detection_start' event
  - When person leaves, WebSocket should emit 'detection_end' event
  - When direction is determined, WebSocket should emit 'direction' event
  - Events should appear in test page's event log

## UI Responsiveness Testing

- [ ] **Dashboard loads quickly**
  - Dashboard should load in under 3 seconds
  - All metrics should populate without errors

- [ ] **UI updates in real-time**
  - Status indicators should update within 1-2 seconds of changes
  - Metrics should update without page refresh
  - Detection toggle buttons should respond immediately

## Performance Optimization Checklist

If experiencing performance issues, consider these adjustments:

- [ ] Reduce camera resolution in config.yaml
- [ ] Lower camera frame rate in config.yaml
- [ ] Use a smaller YOLOv8 model (YOLOv8n instead of YOLOv8s)
- [ ] Lower confidence threshold (to skip some detections)
- [ ] If using Pi 5, consider multiprocessing to utilize another core
- [ ] Ensure logs are properly rotating to avoid disk space issues

## Final Verification

- [ ] System runs stably for at least 30 minutes
- [ ] No memory leaks observed in extended operation
- [ ] Video streaming remains smooth throughout testing
- [ ] Detection and tracking accuracy meets requirements
- [ ] Direction detection accuracy is satisfactory

## Notes

Record any issues, observations, or suggestions for improvement here:

1. 
2. 
3. 

**Test completed by:** ________________  
**Date:** ________________ 