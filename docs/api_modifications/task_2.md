### 2. Summary Endpoint (`/api/metrics/summary?timeRange=7d`)

#### Current Response:
```json
{
    "direction_counts": {
        "left_to_right": 0,
        "right_to_left": 2,
        "unknown": 45
    },
    "period_days": 7,
    "total_detections": 47
}
```

#### Expected Response:
```json
{
    "totalDetections": 47,
    "avgPerDay": 6.7,
    "peakHour": "Not Available",
    "peakCount": 0,
    "change": 0
}
```

#### Required Modifications:
- Rename `total_detections` to `totalDetections`
- Calculate `avgPerDay` by dividing `totalDetections` by `period_days`
- Add `peakHour` and `peakCount` fields (calculated from hourly data)
- Add a `change` field (percentage change from previous period)