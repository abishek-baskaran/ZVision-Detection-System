### 3. Daily Metrics Endpoint (`/api/metrics/daily?timeRange=7d`)

#### Current Response:
```json
{
    "2025-04-02": {
        "detection_count": 2,
        "left_to_right": 0,
        "right_to_left": 0,
        "unknown": 0
    }
}
```

#### Expected Response:
```json
[
    {
        "date": "2025-04-02",
        "count": 2
    }
]
```

#### Required Modifications:
- Transform the object into an array of daily records
- Each daily record should have `date` and `count` fields
- Map `detection_count` to `count`
