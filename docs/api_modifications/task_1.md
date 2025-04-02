### 1. Metrics Endpoint (`/api/metrics?timeRange=7d`)

#### Current Response:
```json
{
    "footfall_count": {
        "entry": 0,
        "exit": 0,
        "unknown": 0
    },
    "hourly": {
        "2025-04-02 05:00": {
            "detection_count": 2,
            "entry": 0,
            "exit": 0,
            "left_to_right": 0,
            "right_to_left": 0,
            "unknown": 0
        }
    },
    "total": {
        "detection_count": 2,
        "direction_counts": {
            "left_to_right": 0,
            "right_to_left": 0,
            "unknown": 0
        }
    }
}
```

#### Expected Response:
```json
{
    "total": 2,
    "change": 0,
    "hourlyData": [
        {
            "hour": "05:00",
            "count": 2
        }
    ],
    "directions": {
        "ltr": 0,
        "rtl": 0,
        "ltrPercentage": 0,
        "rtlPercentage": 0,
        "change": 0
    }
}
```

#### Required Modifications:
- Transform `total.detection_count` to a top-level `total` field
- Add a `change` field (percentage change from previous period)
- Convert `hourly` object to an `hourlyData` array with simplified structure
- Add a `directions` object with directional data and calculated percentages