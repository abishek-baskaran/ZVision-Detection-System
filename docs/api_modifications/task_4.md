# Camera-Specific API Requirements

## Overview

The dashboard requires camera-specific metrics data to properly display analytics for individual cameras. Currently, the API endpoints return aggregated data across all cameras, but we need to add support for filtering by a specific camera.

## Required Modifications

### 1. Add Camera ID Parameter to API Endpoints

The following endpoints should be modified to accept an optional `cam_id` parameter:

| Endpoint | Current URL | Updated URL |
|----------|-------------|------------|
| Metrics | `/api/metrics?timeRange=7d` | `/api/metrics?timeRange=7d&cam_id=1` |
| Summary | `/api/metrics/summary?timeRange=7d` | `/api/metrics/summary?timeRange=7d&cam_id=1` |
| Daily | `/api/metrics/daily?timeRange=7d` | `/api/metrics/daily?timeRange=7d&cam_id=1` |

### 2. Response Format

The response format should remain the same as the current implementation, but the data should be filtered to only include detections from the specified camera:

#### Metrics Endpoint
```json
{
  "change": 0,
  "directions": {
    "change": 0,
    "ltr": 0,
    "ltrPercentage": 0,
    "rtl": 0,
    "rtlPercentage": 0
  },
  "hourlyData": [
    {
      "count": 2,
      "hour": "06:00"
    }
  ],
  "total": 2
}
```

#### Summary Endpoint
```json
{
  "avgPerDay": 6.7,
  "change": 0,
  "peakCount": 2,
  "peakHour": "06:00",
  "totalDetections": 47
}
```

#### Daily Endpoint
```json
[
  {
    "count": 2,
    "date": "2025-04-02"
  }
]
```

### 3. Implementation Notes

- When `cam_id` is provided, filter all metrics to only include data from the specified camera
- When `cam_id` is not provided, return data aggregated across all cameras (current behavior)
- Validate that the provided `cam_id` exists, and return an appropriate error if it doesn't
- The Compare endpoint should continue to return data for all cameras, as its purpose is to compare between cameras

## Priority

This is a high-priority change required for the dashboard to display camera-specific metrics properly. Without this change, users can only see aggregated data across all cameras, which limits the usefulness of the dashboard for installations with multiple cameras.

## Testing

The frontend has been updated to include a camera selection dropdown in the API testing page. This can be used to test the new `cam_id` parameter functionality. 