# ZVision API Modifications for Frontend

This document outlines the discrepancies between the API guide and the actual backend implementation. Please update your frontend to align with these backend endpoints.

## Status Endpoints

**Current (in API guide):**
```
GET /api/status?camera_id={id}
```

**Change to:**
```
GET /api/cameras/{camera_id}/status
```

- The camera_id is now a path parameter, not a query parameter
- For general system status (no camera-specific data), use `GET /api/status`

## Snapshot Endpoints

**Current (in API guide):**
```
GET /api/snapshot/{path}
```

**Change to:**
```
GET /api/snapshot-image/{camera_id}/{filename}
```

- The path structure now requires both camera_id and filename
- Use the new endpoint `GET /api/snapshots/{camera_id}` to first get a list of available snapshots, then use the returned path information to access specific images

## Detections Endpoints

**Current (in API guide):**
```
GET /api/detections/recent?from={date}&to={date}
```

**Change to:**
```
GET /api/detections/recent?count={count}
```

- Replace date range filtering with a simple count parameter
- Default count is 10 if not specified

## Events Endpoints

**Current (in API guide):**
```
GET /api/events?from={date}&to={date}&types={type1}&types={type2}
```

**Change to:**
```
GET /api/events?limit={limit}
```

- Date range and event type filtering is not supported
- Only limit parameter is available to control the number of events returned

## Analytics Endpoints

**Current (in API guide):**
```
GET /api/analytics/compare?timeRange={range}
```

**Change to:**
```
GET /api/analytics/compare?hours={hours}&days={days}
```

- Use hours or days parameters instead of timeRange
- New endpoints available (not in guide):
  - `GET /api/analytics/time-series?camera={camera}&hours={hours}`
  - `GET /api/analytics/heatmap?camera={camera}&width={width}&height={height}`

## Metrics Endpoints

**Current (in API guide):**
```
GET /api/metrics?timeRange={range}
GET /api/metrics/summary?timeRange={range}
GET /api/metrics/daily?timeRange={range}
```

**Change to:**
```
GET /api/metrics?hours={hours}
GET /api/metrics/summary?days={days}
GET /api/metrics/daily?days={days}
```

- Replace timeRange parameter with hours or days parameters
- Response structure differs from the documentation, refer to API responses for exact format

## Camera Endpoints

**Current (in API guide for ROI):**
```
POST /api/cameras/{id}/roi
```
With body:
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

**Change to:**
```
POST /api/cameras/{camera_id}/roi
```
With body:
```json
{
  "x1": 100,
  "y1": 150,
  "x2": 400,
  "y2": 350,
  "entry_direction": "LTR"
}
```

- ROI coordinates are now specified as top-left (x1,y1) and bottom-right (x2,y2) corners
- PATCH endpoint for partial updates is not implemented, use PUT for all updates

## Additional Endpoints (Not in API Guide)

These endpoints are available but not documented in the API guide:

```
GET /video_feed                        - Stream video feed from default camera
GET /video_feed/{camera_id}            - Stream video feed from specific camera
GET /api/frame/current                 - Get current frame as JPEG
GET /api/settings                      - Get system settings
POST /api/detection/start              - Start detection
POST /api/detection/stop               - Stop detection
```

## Missing Endpoints

The following endpoint from the API guide is not implemented:

```
PATCH /api/cameras/{id}                - Partial updates to camera
```

Use the PUT endpoint instead for all updates. 