 # Camera API Documentation

This document provides comprehensive documentation for all camera-related endpoints in the ZVision system.

## Table of Contents
- [Camera Management](#camera-management)
- [Video Streaming](#video-streaming)
- [ROI Configuration](#roi-configuration)
- [Analytics and Snapshots](#analytics-and-snapshots)

## Camera Management

### List All Cameras
```http
GET /api/cameras
```

Returns a list of all configured cameras with their current status.

**Response**
```json
[
  {
    "id": "cam-001",
    "name": "Front Door",
    "source": "rtsp://192.168.1.100:554/stream1",
    "status": "active",
    "person_detected": false
  }
]
```

### Add New Camera
```http
POST /api/cameras
```

Creates a new camera in the system.

**Request Body**
```json
{
  "id": "cam-001",
  "source": "rtsp://192.168.1.100:554/stream1",
  "name": "Front Door",
  "width": 640,
  "height": 480,
  "fps": 30
}
```

**Required Fields**
- `id`: Unique identifier for the camera
- `source`: Camera source URL or device ID

**Optional Fields**
- `name`: Display name for the camera (defaults to "Camera {id}")
- `width`: Frame width
- `height`: Frame height
- `fps`: Frames per second

**Response**
```json
{
  "status": "Camera added",
  "id": "cam-001"
}
```

### Get Camera Details
```http
GET /api/cameras/{camera_id}
```

Returns detailed information about a specific camera.

**Response**
```json
{
  "id": "cam-001",
  "name": "Front Door",
  "source": "rtsp://192.168.1.100:554/stream1",
  "status": "active",
  "person_detected": false,
  "roi": {
    "x1": 100,
    "y1": 150,
    "x2": 400,
    "y2": 350
  },
  "entry_direction": "LTR",
  "resolution": {
    "width": 640,
    "height": 480
  },
  "fps": 30
}
```

### Update Camera
```http
PUT /api/cameras/{camera_id}
```

Updates camera configuration. Note: Source URL cannot be changed after creation.

**Request Body**
```json
{
  "name": "Updated Camera Name",
  "detection_enabled": true
}
```

**Response**
```json
{
  "status": "Camera updated",
  "id": "cam-001"
}
```

### Delete Camera
```http
DELETE /api/cameras/{camera_id}
```

Removes a camera from the system. This will:
1. Stop any active detection
2. Remove the camera from the registry
3. Delete camera configuration from database
4. Clear ROI settings

**Response**
```json
{
  "status": "Camera removed",
  "id": "cam-001"
}
```

### Get Camera Status
```http
GET /api/cameras/{camera_id}/status
```

Returns current operational status of a camera.

**Response**
```json
{
  "id": "cam-001",
  "streaming": true,
  "detection_active": true,
  "person_detected": false,
  "last_detection_time": "2024-03-21T15:30:45Z",
  "direction": "left_to_right",
  "frame_rate": 29.97
}
```

## Video Streaming

### Stream Camera Feed
```http
GET /video_feed/{camera_id}
```

Streams live video feed from the specified camera as MJPEG stream.

**Response**
- Content-Type: multipart/x-mixed-replace; boundary=frame
- Body: MJPEG stream

### Get Current Frame
```http
GET /api/frame/current
```

Returns the latest frame from the camera as a base64 encoded JPEG.

**Response**
```json
{
  "timestamp": "2024-03-21 15:30:45",
  "image_data": "data:image/jpeg;base64,..."
}
```

## ROI Configuration

### Set ROI
```http
POST /api/cameras/{camera_id}/roi
```

Sets the Region of Interest (ROI) and entry direction for a camera.

**Request Body**
```json
{
  "x1": 100,
  "y1": 150,
  "x2": 400,
  "y2": 350,
  "entry_direction": "LTR"
}
```

**Response**
```json
{
  "success": true,
  "message": "ROI configuration saved"
}
```

### Clear ROI
```http
POST /api/cameras/{camera_id}/roi/clear
```

Removes ROI configuration for a camera.

**Response**
```json
{
  "success": true,
  "message": "ROI configuration cleared"
}
```

## Analytics and Snapshots

### Compare Cameras
```http
GET /api/analytics/compare
```

Returns comparative analytics data for all cameras.

**Query Parameters**
- `timeRange` (optional): Time range for data (default: "24h")

**Response**
```json
{
  "cameras": [
    {
      "name": "Front Door",
      "id": "cam-001",
      "count": 425,
      "ltr": 245,
      "rtl": 180
    }
  ]
}
```

### Get Camera Snapshots
```http
GET /api/snapshots/{camera_id}
```

Returns recent detection event snapshots for a camera.

**Query Parameters**
- `limit` (optional): Maximum number of snapshots to return (default: 10)

**Response**
```json
{
  "camera_id": "cam-001",
  "count": 2,
  "snapshots": [
    {
      "id": 1,
      "timestamp": "2024-03-21T15:30:45Z",
      "event_type": "entry",
      "direction": "left_to_right",
      "path": "/path/to/snapshot.jpg",
      "url": "/api/snapshot-image/cam-001/snapshot.jpg"
    }
  ]
}
```

### Get Snapshot Image
```http
GET /api/snapshot-image/{camera_id}/{filename}
```

Returns a specific snapshot image.

**Response**
- Content-Type: image/jpeg
- Body: JPEG image data

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request
```json
{
  "error": "Missing required fields: id and source"
}
```

### 404 Not Found
```json
{
  "error": "Camera cam-001 not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "Camera registry not available"
}
```

## Notes and Limitations

1. Camera source URLs cannot be changed after creation. To change the source, delete and recreate the camera.
2. Video streams are limited to 20 FPS maximum to control bandwidth usage.
3. Snapshot storage location and retention policy is configured server-side.
4. ROI coordinates are specified as top-left (x1,y1) and bottom-right (x2,y2) corners.
5. Entry direction must be either "LTR" (left-to-right) or "RTL" (right-to-left).
6. Analytics data is cached and updated every minute to improve performance. 