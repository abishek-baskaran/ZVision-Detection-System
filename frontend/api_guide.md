# ZVision API Guide

This document provides information on available API endpoints for the ZVision system.

## General Information

- All endpoints follow RESTful conventions
- All response data is in JSON format
- Most API calls include a simulated delay to mimic real-world behavior

## Status Endpoints

### Get Detection Status

```
GET /api/status?camera_id={id}
```

Returns detection status for a specific camera.

**Query Parameters:**
- `camera_id` - The ID of the camera to check

**Response:**
```json
{
  "detection_active": true,
  "person_detected": true,
  "last_detection_time": "2023-04-07T15:40:22Z",
  "camera_id": "cam-001",
  "direction": "LTR"
}
```

## Snapshot Endpoints

### Get Snapshot

```
GET /api/snapshot/{path}
```

Retrieves a snapshot image with the specified path.

**Parameters:**
- `path` - Path identifier for the snapshot

**Response:**
```json
{
  "success": true,
  "message": "Snapshot with path {path} would be returned here",
  "path": "/snapshots/{path}"
}
```

## Detections Endpoints

### Get Recent Detections

```
GET /api/detections/recent?from={date}&to={date}
```

Returns a list of recent detections.

**Query Parameters:**
- `from` (optional) - Start date (ISO format)
- `to` (optional) - End date (ISO format)

**Response:**
```json
[
  {
    "id": "det-001",
    "timestamp": "2023-04-07T08:30:15Z",
    "camera_id": "cam-001",
    "direction": "LTR",
    "confidence": 0.92,
    "snapshot_path": "/snapshots/det-001.jpg"
  },
  ...
]
```

## Events Endpoints

### Get System Events

```
GET /api/events?from={date}&to={date}&types={type1}&types={type2}
```

Returns system events filtered by date and event types.

**Query Parameters:**
- `from` (optional) - Start date (ISO format)
- `to` (optional) - End date (ISO format)
- `types` (optional, repeatable) - Event types to include (system, error, config)

**Response:**
```json
[
  {
    "id": "evt-001",
    "timestamp": "2023-04-07T08:23:15Z",
    "event_type": "system",
    "message": "System started",
    "camera_id": null
  },
  ...
]
```

## Analytics Endpoints

### Get Camera Comparison

```
GET /api/analytics/compare?timeRange={range}
```

Returns comparison data for all cameras.

**Query Parameters:**
- `timeRange` (optional) - Time range for data (default: "7d")

**Response:**
```json
{
  "cameras": [
    {
      "name": "Front Door",
      "id": "cam-001",
      "count": 425,
      "ltr": 245,
      "rtl": 180
    },
    ...
  ]
}
```

## Metrics Endpoints

### Get Overview Metrics

```
GET /api/metrics?timeRange={range}
```

Returns overall detection metrics.

**Query Parameters:**
- `timeRange` (optional) - Time range for data (default: "7d")

**Response:**
```json
{
  "total": 1248,
  "change": 12.5,
  "hourlyData": [...],
  "directions": {
    "ltr": 742,
    "rtl": 506,
    "ltrPercentage": 59.5,
    "rtlPercentage": 40.5,
    "change": 5.2
  }
}
```

### Get Summary Metrics

```
GET /api/metrics/summary?timeRange={range}
```

Returns summary metrics for detections.

**Query Parameters:**
- `timeRange` (optional) - Time range for data (default: "7d")

**Response:**
```json
{
  "totalDetections": 1248,
  "avgPerDay": 178,
  "peakHour": "12:00 - 13:00",
  "peakCount": 78,
  "change": 8.3
}
```

### Get Daily Metrics

```
GET /api/metrics/daily?timeRange={range}
```

Returns daily detection counts.

**Query Parameters:**
- `timeRange` (optional) - Time range for data (default: "7d")

**Response:**
```json
[
  {
    "date": "2023-04-01",
    "count": 150
  },
  ...
]
```

## Detection Control Endpoints

### Start Detection

```
POST /api/detection/start
```

Starts the global detection system.

**Response:**
```json
{
  "success": true,
  "message": "Detection started successfully"
}
```

### Stop Detection

```
POST /api/detection/stop
```

Stops the global detection system.

**Response:**
```json
{
  "success": true,
  "message": "Detection stopped successfully"
}
```

## Camera Endpoints

### List All Cameras

```
GET /api/cameras
```

Returns a list of all cameras.

**Response:**
```json
[
  {
    "id": "cam-001",
    "name": "Front Door",
    "source": "rtsp://192.168.1.100:554/stream1",
    "active": true,
    "detection_enabled": true,
    "roi": {
      "x": 50,
      "y": 100,
      "width": 200,
      "height": 150
    },
    "entry_direction": "LTR"
  },
  ...
]
```

### Add New Camera

```
POST /api/cameras
```

Creates a new camera.

**Request Body:**
```json
{
  "id": "cam-006",
  "name": "New Camera",
  "source": "rtsp://192.168.1.105:554/stream1"
}
```

**Response:**
```json
{
  "id": "cam-006",
  "name": "New Camera",
  "source": "rtsp://192.168.1.105:554/stream1",
  "active": true,
  "detection_enabled": false
}
```

### Get Camera Details

```
GET /api/cameras/{id}
```

Returns details for a specific camera.

**Parameters:**
- `id` - The ID of the camera

**Response:**
```json
{
  "id": "cam-001",
  "name": "Front Door",
  "source": "rtsp://192.168.1.100:554/stream1",
  "active": true,
  "detection_enabled": true,
  "roi": {
    "x": 50,
    "y": 100,
    "width": 200,
    "height": 150
  },
  "entry_direction": "LTR"
}
```

### Update Camera

```
PUT /api/cameras/{id}
```

Completely updates a camera with new data.

**Parameters:**
- `id` - The ID of the camera

**Request Body:**
```json
{
  "name": "Updated Camera Name",
  "source": "rtsp://192.168.1.100:554/stream1",
  "active": true,
  "detection_enabled": true
}
```

**Response:**
The updated camera object

### Update Camera (Partial)

```
PATCH /api/cameras/{id}
```

Partially updates a camera with new data.

**Parameters:**
- `id` - The ID of the camera

**Request Body:**
```json
{
  "name": "Updated Camera Name"
}
```

**Response:**
The updated camera object

### Delete Camera

```
DELETE /api/cameras/{id}
```

Deletes a camera.

**Parameters:**
- `id` - The ID of the camera

**Response:**
204 No Content

### Set Camera ROI

```
POST /api/cameras/{id}/roi
```

Sets the region of interest (ROI) for a camera.

**Parameters:**
- `id` - The ID of the camera

**Request Body:**
```json
{
  "roi": {
    "x": 100,
    "y": 150,
    "width": 300,
    "height": 200
  },
  "entry_direction": "LTR"
}
```

**Response:**
The updated camera object

### Clear Camera ROI

```
POST /api/cameras/{id}/roi/clear
```

Clears the region of interest (ROI) for a camera.

**Parameters:**
- `id` - The ID of the camera

**Response:**
The updated camera object 