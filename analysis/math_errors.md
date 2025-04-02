# Mathematical and Logical Errors Analysis

## 1. Analytics Engine (analytics_engine.py)

### Error: Incorrect Dummy Data Generation
- **Location**: `get_camera_entry_counts()`, `generate_dummy_time_series()`
- **Issue**: 
  - Random data generation (5-15) during errors skews analytics
  - Dummy time series uses camera_id as seed but same pattern repeats hourly
- **Impact**: 
  - Fake data contaminates real metrics
  - Hourly patterns become predictable across days
- **Fix**: 
  - Separate error state from data generation
  - Use time-based seeds for randomness

## 2. Camera Manager (camera_manager.py)

### Error: Frame Timing Calculation
- **Location**: `_capture_loop()` video FPS handling
- **Issue**:
  ```python
  video_fps = cap.get(cv2.CAP_PROP_FPS)
  frame_delay = 1.0 / video_fps  # Division by zero risk
  ```
- **Impact**: Potential division by zero if video FPS is 0
- **Fix**: Add validation:
  ```python
  video_fps = max(video_fps, 1) if not self.is_video_file else 1
  ```

## 3. Dashboard Manager (dashboard_manager.py)

### Error: Time Window Calculation
- **Location**: `get_hourly_metrics()`, `get_daily_metrics()`
- **Issue**:
  - Uses naive datetime comparisons without timezone awareness
  - Aggregates hours by string comparison ("2024-04-01 10:00" > "2024-03-31 23:00")
- **Impact**: Incorrect time window selection across day boundaries
- **Fix**: Use epoch timestamps for comparisons

## 4. Detection Manager (detection_manager.py)

### Error: Direction Calculation
- **Location**: `_update_direction()`
- **Issue**:
  - Uses absolute position threshold (50 pixels)
  - Hardcoded threshold doesn't account for ROI size
  ```python
  if abs(current - self.position_history[camera_id][0]) > 50:
  ```
- **Impact**: Direction detection accuracy varies with resolution
- **Fix**: Make threshold relative to ROI width

## 5. Database Manager (database_manager.py)

### Error: Date Filtering
- **Location**: `get_detection_count_by_direction()`
- **Issue**:
  ```python
  date_threshold = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
  ```
  - Truncates time component, includes extra day
- **Impact**: Returns 1 more day than requested
- **Fix**: Use exact timestamp:
  ```python
  date_threshold = datetime.now() - timedelta(days=days)
  ```

## 6. Storage Manager (storage_manager.py)

### Error: FIFO Cleanup
- **Location**: `_enforce_fifo_for_dir()`
- **Issue**:
  ```python
  files.sort(key=lambda x: os.path.getmtime(str(x)))
  ```
  - Uses modification time instead of creation time
- **Impact**: Might delete newest files if modified
- **Fix**: Use creation time with fallback:
  ```python
  getctime() if platform.system() == 'Windows' else getmtime()
  ```

## 7. Common Pattern Issues

### Error: Thread Safety
- **Locations**: Multiple managers
- **Issue**: Mixed use of `RLock` and regular `Lock`
- **Impact**: Potential deadlocks in camera initialization
- **Fix**: Standardize on context managers for all locks

### Error: Floating Point Precision
- **Locations**: Multiple timing calculations
- **Issue**: Reliance on `time.time()` for durations
- **Impact**: Clock drift affects metrics
- **Fix**: Use monotonic timers:
  ```python 
  time.monotonic()
  ```

## 8. Coordinate System Issues

### Error: ROI Handling
- **Location**: `database_manager.py` ROI storage
- **Issue**: Stores absolute coordinates instead of relative
- **Impact**: ROI breaks with resolution changes
- **Fix**: Store as percentages of frame size

## Recommended Improvements

1. Add validation layer for all mathematical inputs
2. Implement unit tests for edge cases:
   - Zero-time intervals
   - Empty databases
   - Full disk scenarios
3. Create central time service for consistent timing
4. Add dimensional analysis for pixel operations
5. Implement camera calibration metrics 