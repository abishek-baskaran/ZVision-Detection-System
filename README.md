# ZVision Detection System

A person detection system for Raspberry Pi that detects people, counts footfall, and tracks movement direction using YOLOv8 and OpenCV.

## Project Overview

ZVision is a comprehensive detection system that leverages computer vision to:

1. Detect people in a video stream
2. Track movement direction (left-to-right or right-to-left)
3. Count footfall (number of people passing by)
4. Provide real-time WebSocket notifications
5. Offer a web dashboard for monitoring

The system is optimized for Raspberry Pi and balances performance with accuracy by using adaptive processing rates based on detection state.

## Directory Structure

```
zvision/
├── config.yaml            # Configuration file
├── main.py                # Main application entry point
├── start_server.py        # Server startup script with threading mode
├── managers/              # Core system components
│   ├── api_manager.py     # API and WebSocket server
│   ├── camera_manager.py  # Camera feed handling
│   ├── dashboard_manager.py # Dashboard data processing
│   ├── database_manager.py # SQLite database management
│   ├── detection_manager.py # YOLOv8 detection processing
│   └── resource_provider.py # Configuration and logging
├── models/                # YOLOv8 model files
├── static/                # Web static assets (HTML, CSS, JS)
│   └── test_page.html     # WebSocket test page
├── database/              # Database directory
│   └── zvision.db         # SQLite database file
├── logs/                  # Log files directory
└── tests/                 # Testing materials
    ├── performance/       # Performance and concurrency testing scripts
    ├── manual/            # Manual testing checklists
    ├── scripts/           # Utility scripts for testing
    ├── unit/              # Unit tests for individual components
    └── README.md          # Testing documentation
```

## Getting Started

### Prerequisites

- Raspberry Pi (recommended: Pi 4 or Pi 5)
- Camera module or USB webcam
- Python 3.7+
- Required libraries (see requirements.txt)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/username/zvision.git
   cd zvision
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Download a YOLOv8 model (if not included):
   ```bash
   mkdir -p models
   # For YOLOv8n (nano - fastest)
   wget -O models/yolov8n.pt https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
   ```

5. Update the `config.yaml` file with your settings.

### Configuration

The system is configured via the `config.yaml` file, which includes settings for:

- **Camera**: Device ID, resolution, frame rate
  ```yaml
  camera:
    device_id: 0
    width: 640
    height: 480
    fps: 30
  ```

- **Detection**: Model settings, confidence thresholds, processing rates
  ```yaml
  detection:
    model_path: "models/yolov8n.pt"
    confidence_threshold: 0.5
    idle_fps: 1
    active_fps: 5
  ```

- **API Server**: Host, port, debug mode
  ```yaml
  api:
    host: "0.0.0.0"
    port: 5000
    debug: false
  ```

- **Database**: Path and settings
  ```yaml
  database:
    path: "database/zvision.db"
  ```

- **Logging**: Log levels, rotation settings
  ```yaml
  logging:
    level: "INFO"
    file: "logs/zvision.log"
    max_size_mb: 10
    backup_count: 5
  ```

### Running the System

Start the detection system:

```bash
python start_server.py
```

The system will:
1. Initialize all components (camera, detection, database, dashboard, API)
2. Start the camera feed
3. Load the YOLOv8 model
4. Begin person detection at the configured frame rate
5. Start the web server for the dashboard and API

Access the dashboard by navigating to:
- http://localhost:5000/ (replace localhost with your Pi's IP if accessing remotely)

The test page for WebSocket notifications is available at:
- http://localhost:5000/test

## API Endpoints

The system provides the following RESTful API endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Current system status, detection state, and dashboard summary |
| `/api/events` | GET | Recent events from the database |
| `/api/detections/recent` | GET | Recent detection events with details |
| `/api/metrics` | GET | System metrics including hourly data and footfall count |
| `/api/metrics/daily` | GET | Metrics aggregated by day |
| `/api/metrics/summary` | GET | Cumulative metrics over time by direction |
| `/api/settings` | GET | System settings from config |
| `/api/detection/start` | POST | Start the detection process |
| `/api/detection/stop` | POST | Stop the detection process |
| `/api/frame/current` | GET | Current camera frame as JPEG image |
| `/video_feed` | GET | MJPEG streaming video feed |

## WebSocket Notifications

Real-time events are pushed to clients via WebSocket:

| Event | Description |
|-------|-------------|
| `detection_start` | Fired when a person is first detected |
| `detection_end` | Fired when a person is no longer detected |
| `direction` | Fired when a direction is determined (left-to-right/right-to-left) |

Connect to these events using the Socket.IO client library. See the test page for an example implementation.

## Testing

The system includes comprehensive testing tools:

### Performance Testing

```bash
# Install testing dependencies
./tests/scripts/install_test_dependencies.sh

# Run performance and concurrency tests
python tests/performance/test_performance.py

# Test specific aspects
python tests/performance/test_performance.py --test status
python tests/performance/test_performance.py --test concurrency
python tests/performance/test_performance.py --test toggle
python tests/performance/test_performance.py --test database
python tests/performance/test_performance.py --test resources
```

### Manual Testing

Follow the checklist at `tests/manual/test_checklist.md` for comprehensive functionality testing, which includes:

- Idle mode testing
- Person detection verification
- Direction tracking
- WebSocket notifications
- Resource usage monitoring
- Database verification

### Unit Testing

Run individual unit tests to verify component functionality:

```bash
# Run all unit tests
python -m unittest discover tests/unit

# Run a specific test
python -m unittest tests/unit/test_detection_manager.py
```

## System Architecture

ZVision follows a modular design pattern with these key components:

- **ResourceProvider**: Central configuration and logging management
- **CameraManager**: Handles camera initialization and frame capture
- **DetectionManager**: Processes frames with YOLOv8 and tracks directions
- **DashboardManager**: Aggregates metrics and analytics
- **DatabaseManager**: Handles persistent storage of events
- **APIManager**: Provides web dashboard and REST API with WebSocket

The system uses threading for concurrency, with separate threads for:
- Camera frame capture
- Person detection processing
- Web server and API handling

## Features

- **Adaptive Frame Processing**: 1 FPS in idle mode, 5+ FPS when people are detected
- **Direction Detection**: Tracks movement direction using centroid tracking
- **Real-time Notifications**: WebSocket events for immediate updates
- **Performance Optimization**: Balances accuracy and resource usage
- **Dashboard**: Visual monitoring of detections and statistics
- **RESTful API**: Integration with other systems
- **Database Logging**: Persistent storage of all detection events
- **Configurable**: Easily adjust all parameters via config.yaml

## Troubleshooting

- **Camera Issues**: Verify the camera device ID in config.yaml and check permissions
- **Model Loading**: Ensure the YOLOv8 model file exists in the models directory
- **Performance**: If CPU usage is high, try a smaller model or reduce resolution/FPS
- **WebSocket**: If notifications aren't working, check browser console for connection errors
- **API Access**: For remote access, ensure the host is set to "0.0.0.0" in config.yaml

## License

[Specify the license under which your project is released]

## Acknowledgments

- YOLOv8 by Ultralytics for efficient object detection
- OpenCV community for computer vision tools
- Flask and Flask-SocketIO for the web interface
- SQLite for lightweight database storage 