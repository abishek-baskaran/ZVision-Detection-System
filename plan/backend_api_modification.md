# Backend Modification Suggestions

This document outlines recommended modifications to the backend API that would simplify the frontend-backend integration.

## Time Range Parameter Support

**Current Issue:**
- Frontend uses a simple `timeRange` parameter (e.g., "24h", "7d")
- Backend requires explicit `hours` or `days` parameters
- We've implemented transformation functions but direct support would be cleaner

**Suggested Modification:**
- Add support for a `timeRange` parameter on endpoints that currently use hours/days:
  - `/api/metrics`
  - `/api/metrics/summary`
  - `/api/metrics/daily`
  - `/api/analytics/compare`

## Date Range Filtering for Events

**Current Issue:**
- Frontend has endpoints that expect date range filtering (`from`/`to` dates)
- Backend only supports a `limit` parameter for the events endpoint

**Suggested Modification:**
- Add support for date range filtering on the events endpoint:
  ```
  GET /api/events?from=2023-04-01&to=2023-04-07
  ```
