# Phase 4: Multi-Camera Support & Advanced Analytics

## Overview

Building on the successful implementation of the Region of Interest (ROI) functionality in Phase 3, Phase 4 will expand the ZVision system to support multiple cameras simultaneously and introduce advanced analytics capabilities. This phase will transform the system from a single-camera solution into a comprehensive multi-point detection network with rich analytical insights.

## Goals

1. **Multi-Camera Support**: Enable the system to connect to, manage, and process feeds from multiple cameras simultaneously.
2. **Independent Camera Configuration**: Allow each camera to have its own settings, ROI, and direction mapping.
3. **Enhanced Analytics**: Implement advanced metrics, comparative analysis, and visualization tools.
4. **Unified Dashboard**: Create an integrated view for managing multiple camera feeds and analytics.
5. **Resource Optimization**: Ensure efficient CPU/memory usage even with multiple detection pipelines.

## Component Enhancements

### 1. CameraManager Upgrades

- **Camera Registry System**: Implement a registry to add, remove, and manage multiple camera sources
- **Multi-Feed Processing**: Modify frame capture loops to handle concurrent streams
- **Connection Management**: Add automatic reconnection and health monitoring for all camera streams
- **Dynamic Resource Allocation**: Implement adaptive frame rate control based on system load

```python
# Camera registry concept
class CameraRegistry:
    def __init__(self):
        self.cameras = {}  # Dictionary of camera_id: CameraManager instances
        
    def add_camera(self, camera_id, connection_string, name=None, enabled=True):
        # Create and register a new camera
        pass
        
    def remove_camera(self, camera_id):
        # Safely remove a camera instance
        pass
```

### 2. DetectionManager Enhancements

- **Per-Camera Detection Pipelines**: Create independent detection processes for each camera
- **Resource Scheduling**: Implement intelligent scheduling to balance processing across cameras
- **Unified State Management**: Maintain aggregated and per-camera detection states
- **Prioritization System**: Allow critical cameras to receive more processing resources

```python
# Detection manager modifications
class DetectionManager:
    def __init__(self, resource_provider, camera_registry, dashboard_manager=None, db_manager=None):
        self.camera_registry = camera_registry
        self.detection_threads = {}  # Dictionary of camera_id: detection thread
        # ... existing initialization ...
        
    def start_all(self):
        # Start detection for all enabled cameras
        pass
        
    def start_camera(self, camera_id):
        # Start detection for a specific camera
        pass
```

### 3. Database Enhancements

- **Multi-Camera Schema**: Extend all relevant tables with camera_id indexing
- **Optimized Queries**: Design efficient queries for cross-camera analytics
- **Data Aggregation**: Add functions for time-based and cross-camera data aggregation
- **Storage Optimization**: Implement data retention and archiving policies

```sql
-- Example of enhanced event table
CREATE TABLE IF NOT EXISTS detection_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    direction TEXT,
    confidence REAL,
    details TEXT,
    -- Add indices for efficient querying
    INDEX idx_camera_timestamp (camera_id, timestamp)
);
```

### 4. Dashboard Manager Extensions

- **Cross-Camera Analytics**: Implement metrics that span multiple cameras
- **Time-Series Analysis**: Add hourly, daily, weekly, and monthly pattern detection
- **Traffic Flow Visualization**: Create heatmaps and flow diagrams for movement patterns
- **Comparative Reporting**: Enable comparison between different cameras or time periods
- **Custom Metric Builder**: Allow users to define and save custom analytics views

```python
class DashboardManager:
    # ... existing methods ...
    
    def get_cross_camera_metrics(self, time_period="day", cameras=None):
        # Return metrics aggregated across multiple cameras
        pass
        
    def get_traffic_patterns(self, camera_id=None, period="week"):
        # Return time-based patterns for visualization
        pass
```

### 5. UI Enhancements

- **Multi-Camera Viewer**: Create a grid view to monitor multiple feeds simultaneously
- **Camera Selector**: Add UI controls to switch between camera feeds and configurations
- **Camera Management Panel**: Provide interface for adding, removing, and configuring cameras
- **Enhanced Analytics Dashboard**: Design charts and visualizations for advanced metrics
- **Custom Dashboard Layouts**: Allow users to create personalized dashboard layouts

## API Additions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/cameras` | GET | List all configured cameras |
| `/api/cameras` | POST | Add a new camera to the system |
| `/api/cameras/<camera_id>` | GET | Get configuration for a specific camera |
| `/api/cameras/<camera_id>` | PUT | Update camera configuration |
| `/api/cameras/<camera_id>` | DELETE | Remove a camera from the system |
| `/api/cameras/<camera_id>/status` | GET | Get operational status of a camera |
| `/api/analytics/compare` | GET | Get comparative metrics between cameras |
| `/api/analytics/time-series` | GET | Get time-based analytics with patterns |
| `/api/dashboard/layouts` | GET | Get saved dashboard layouts |
| `/api/dashboard/layouts` | POST | Save a new dashboard layout |

## Implementation Strategy

The implementation will follow this sequence:

1. **Database Schema Updates**: First, modify the database to support multi-camera data
2. **CameraManager Refactoring**: Implement the camera registry and multi-feed support
3. **DetectionManager Modifications**: Enable per-camera detection pipelines
4. **API Endpoint Extensions**: Add the new multi-camera API endpoints
5. **Analytics Engine Development**: Implement the enhanced analytics capabilities
6. **UI Updates**: Develop the multi-camera dashboard interface

## Resource Considerations

To ensure the Raspberry Pi can handle multiple camera streams:

- **Adaptive Processing**: Automatically adjust frame rates based on system load
- **Configurable Quality**: Allow quality/resolution settings per camera
- **Processing Priorities**: Enable prioritization of certain cameras over others
- **Resource Monitoring**: Add system monitoring to prevent overload
- **Optional Hardware Acceleration**: Add support for hardware acceleration where available

## Testing Strategy

Testing will focus on:

1. **Performance Testing**: Verify system stability with multiple camera streams
2. **Accuracy Validation**: Ensure detection accuracy is maintained across cameras
3. **Resource Usage**: Monitor CPU, memory, and network usage under various loads
4. **UI Responsiveness**: Test dashboard performance with multiple active feeds
5. **Analytics Verification**: Validate correctness of new analytical metrics

## Future Expansion

This phase will lay groundwork for potential future enhancements:

- **Cloud Integration**: Syncing data to cloud services for backup or remote access
- **Mobile Applications**: Companion apps for remote monitoring
- **Advanced AI**: Additional detection types or behavior analysis
- **Alert Systems**: Configurable notifications for specific events
- **Integration APIs**: Connecting with third-party systems (access control, etc.) 