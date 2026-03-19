# Frontend Dashboard API Integration Guide

This document outlines all the API endpoints required to fully integrate the frontend dashboard with the backend.

## Base URL
All endpoints should be prefixed with `/api/v1/`

## Authentication
All endpoints require Bearer token authentication via `Authorization` header:
```
Authorization: Bearer {access_token}
```

---

## Task Streaming (Current Backend Contract)

These are the active endpoints used by async agent runs and realtime UI updates.

### POST `/api/v1/agent/ask`
Queue a new async task.

**Request Body:**
```json
{
  "query": "Analyze this dataset",
  "session_id": "optional-session-id",
  "file_id": "optional-file-id",
  "language": "fr"
}
```

**Response:**
```json
{
  "task_id": "uuid",
  "session_id": "string",
  "status": "queued",
  "message": "Request being processed..."
}
```

### GET `/api/v1/agent/status/{task_id}`
Polling fallback endpoint.

**Response (running):**
```json
{
  "task_id": "uuid",
  "status": "STARTED"
}
```

**Response (cached terminal fallback):**
```json
{
  "task_id": "uuid",
  "status": "COMPLETED",
  "cached": true,
  "payload": {
    "status": "completed",
    "progress_percent": 100,
    "token_count_total": 123,
    "result": {}
  }
}
```

### POST `/api/v1/agent/cancel/{task_id}`
Best-effort cancel for running task.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "canceled",
  "message": "Task cancellation requested."
}
```

### GET `/api/v1/agent/task/{task_id}/summary`
Unified frontend-friendly state endpoint.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "terminal": true,
  "source": "celery|cache",
  "can_cancel": false,
  "result": {},
  "error": null,
  "payload": {}
}
```

### GET `/api/v1/agent/history/cache?limit=20`
Recent cached terminal payloads for current user.

**Response:**
```json
{
  "history": [
    {
      "task_id": "uuid",
      "payload": {
        "status": "completed",
        "progress_percent": 100,
        "token_count_total": 250,
        "result": {}
      }
    }
  ],
  "count": 1,
  "limit": 20
}
```

### WebSocket `/api/v1/ws/{task_id}?token={access_token}`
Realtime progress stream.

**Progress payload fields to consume in frontend:**
- `status`: `started|processing|retrying|completed|failed|canceled`
- `type`: `started|processing|progress|result|error|heartbeat`
- `progress_percent`: integer (0-100)
- `eta_seconds`: integer or null
- `can_cancel`: boolean
- `reconnect_after_seconds`: integer
- `token_count_input`, `token_count_output`, `token_count_total`: integers
- `emitted_at`: unix timestamp (seconds)

**Heartbeat example:**
```json
{
  "status": "processing",
  "type": "heartbeat",
  "task_id": "uuid",
  "message": "Waiting for task updates",
  "can_cancel": true,
  "reconnect_after_seconds": 3,
  "emitted_at": 1773912000
}
```

---

## 1. History Endpoints

### GET `/api/history`
Fetch paginated history of queries with filtering.

**Query Parameters:**
- `page` (integer, required): Page number (1-indexed)
- `page_size` (integer, required): Items per page
- `date_range` (string, required): `last_24h`, `last_7d`, `all`
- `status` (string, required): `all`, `SUCCESS`, `FAILURE`
- `query` (string, optional): Search query

**Response:**
```json
{
  "queries": [
    {
      "id": "string",
      "query": "string",
      "result": "string",
      "timestamp": "ISO8601",
      "status": "SUCCESS|FAILURE",
      "model_used": "string",
      "confidence": 0.95
    }
  ],
  "total_count": 100,
  "page": 1,
  "page_size": 10
}
```

### POST `/api/history/{history_id}/rerun`
Re-execute a previous query.

**Response:**
```json
{
  "task_id": "string"
}
```

### DELETE `/api/history/{history_id}`
Delete a specific history item.

### DELETE `/api/history`
Clear all history items.

### GET `/api/history/export`
Export history as file.

**Query Parameters:**
- `format` (string, required): `csv`, `json`

**Response:** File blob

---

## 2. Export Endpoints

### GET `/api/exports/stats`
Get export statistics.

**Response:**
```json
{
  "total_queries": 42,
  "total_models": 15,
  "total_results": 127,
  "last_export": "ISO8601",
  "storage_used": "16.2 MB"
}
```

### GET `/api/exports/{option_id}`
Export specific data category.

**Query Parameters:**
- `format` (string, required): `csv`, `json`, `excel`

**Supported option_ids:**
- `history`
- `settings`
- `models`
- `results`

**Response:** File blob

### GET `/api/exports/all`
Export all data.

**Query Parameters:**
- `format` (string, required): `csv`, `json`, `excel`

**Response:** File blob (zip or individual files)

---

## 3. Settings Endpoints

### GET `/api/settings`
Get user settings.

**Response:**
```json
{
  "id": "string",
  "user_id": "string",
  "language": "fr|en",
  "theme": "dark|light",
  "notifications_enabled": true,
  "email_notifications": true,
  "default_model": "string",
  "temperature": 0.7,
  "max_tokens": 2048,
  "sidebar_collapsed": false,
  "auto_save_enabled": true,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### PUT `/api/settings`
Update user settings.

**Request Body:**
```json
{
  "language": "fr|en",
  "theme": "dark|light",
  "notifications_enabled": true,
  "email_notifications": true,
  "default_model": "string",
  "temperature": 0.7,
  "max_tokens": 2048,
  "sidebar_collapsed": false,
  "auto_save_enabled": true
}
```

### POST `/api/settings/password`
Change password.

**Request Body:**
```json
{
  "current_password": "string",
  "new_password": "string"
}
```

### POST `/api/settings/2fa/enable`
Enable two-factor authentication.

**Response:**
```json
{
  "secret": "string",
  "qr_code": "string (base64)"
}
```

### POST `/api/settings/2fa/disable`
Disable two-factor authentication.

**Request Body:**
```json
{
  "code": "string (6-digit code)"
}
```

### GET `/api/settings/export`
Export all user settings as file.

**Response:** File blob

### DELETE `/api/account`
Delete user account and all associated data.

**Request Body:**
```json
{
  "password": "string"
}
```

---

## 4. Account Endpoints

### GET `/api/account`
Get account information.

**Response:**
```json
{
  "id": "string",
  "email": "string",
  "name": "string",
  "profile_picture_url": "string|null",
  "created_at": "ISO8601",
  "subscription_plan": "free|pro|enterprise",
  "provider_type": "password|oauth",
  "two_factor_enabled": true,
  "is_verified": true,
  "preferred_language": "fr|en"
}
```

### POST `/api/account/profile`
Update profile information (multipart/form-data).

**Request Body:**
- `name` (string, optional)
- `profile_picture` (file, optional)

**Response:** Updated account object

### GET `/api/account/api-keys`
Get all API keys for user.

**Response:**
```json
[
  {
    "id": "string",
    "name": "string",
    "key": "string",
    "shortKey": "string",
    "created_at": "ISO8601",
    "last_used": "ISO8601|null",
    "is_active": true,
    "expires_at": "ISO8601|null"
  }
]
```

### POST `/api/account/api-keys`
Create a new API key.

**Request Body:**
```json
{
  "name": "string"
}
```

**Response:** API key object

### PUT `/api/account/api-keys/{key_id}/regenerate`
Regenerate an existing API key.

**Response:** New API key object

### DELETE `/api/account/api-keys/{key_id}`
Delete an API key.

### GET `/api/account/sessions`
Get all active sessions.

**Response:**
```json
[
  {
    "id": "string",
    "device": "string",
    "browser": "string",
    "lastActive": "ISO8601",
    "isCurrent": true,
    "ipAddress": "string"
  }
]
```

### POST `/api/account/sessions/logout-all`
Logout from all sessions.

### DELETE `/api/account/sessions/{session_id}`
Logout from a specific session.

---

## 5. GDPR Endpoints

### GET `/api/gdpr/export`
Export all personal data as file.

**Response:** File blob (JSON/ZIP format)

### DELETE `/api/gdpr/delete`
Delete all personal data.

**Response:**
```json
{
  "message": "All data deleted successfully"
}
```

### GET `/api/gdpr/consent`
Get user consent status.

**Response:**
```json
{
  "analytics": true,
  "marketing": false,
  "necessary": true,
  "timestamp": "ISO8601"
}
```

### PUT `/api/gdpr/consent`
Update consent preferences.

**Request Body:**
```json
{
  "analytics": true,
  "marketing": false,
  "necessary": true
}
```

---

## 6. Documentation Endpoints

### GET `/api/docs/faq/search`
Search FAQs.

**Query Parameters:**
- `q` (string, required): Search query

**Response:**
```json
[
  {
    "id": "string",
    "category": "string",
    "question": "string",
    "answer": "string",
    "tags": ["string"]
  }
]
```

### GET `/api/docs/tutorials`
Get all tutorials.

**Response:**
```json
[
  {
    "id": "string",
    "title": "string",
    "description": "string",
    "duration": "string",
    "difficulty": "beginner|intermediate|advanced",
    "videoUrl": "string",
    "lastUpdated": "ISO8601",
    "tags": ["string"]
  }
]
```

### GET `/api/docs/tutorials/{tutorial_id}`
Get specific tutorial.

### GET `/api/docs/api`
Get API documentation.

---

## 7. Analytics Endpoints (Fire-and-Forget)

### POST `/api/analytics/events`
Track custom events.

**Request Body:**
```json
{
  "event": "string",
  "data": {}
}
```

### POST `/api/analytics/pageviews`
Track page views.

**Request Body:**
```json
{
  "page": "string"
}
```

---

## Error Responses

All endpoints should return error responses in this format:

```json
{
  "error": "string",
  "message": "string",
  "statusCode": 400,
  "details": {}
}
```

### Common Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `409`: Conflict
- `422`: Unprocessable Entity
- `429`: Too Many Requests
- `500`: Internal Server Error

---

## Rate Limiting

Recommended rate limits:
- General endpoints: 100 requests/minute
- Export endpoints: 10 requests/minute
- Analytics endpoints: No limit (fire-and-forget)

Include in response headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1234567890
```

---

## Implementation Notes

1. **File Uploads**: Profile pictures should be stored and served from CDN
2. **API Keys**: Should be hashed like passwords, never stored in plain text
3. **2FA**: Recommend TOTP (Time-based One-Time Password)
4. **Export Files**: Should be generated asynchronously for large datasets
5. **Pagination**: Default page size should be 10-20 items
6. **Dates**: Always use ISO8601 format in UTC
7. **Session Management**: Use HTTP-only cookies for session tokens

---

## Development Checklist

- [ ] Implement all history endpoints
- [ ] Implement all export endpoints
- [ ] Implement all settings endpoints
- [ ] Implement all account endpoints
- [ ] Implement GDPR compliance endpoints
- [ ] Implement documentation endpoints
- [ ] Add proper error handling
- [ ] Add rate limiting
- [ ] Add request validation
- [ ] Add response compression
- [ ] Add CORS headers
- [ ] Add request logging
- [ ] Add API documentation (Swagger/OpenAPI)
- [ ] Setup webhook for async exports
- [ ] Add database migrations
- [ ] Setup data encryption

---

## Frontend Implementation Status

✅ All frontend pages created
✅ All hooks and utilities implemented
✅ Mock API functions ready
✅ Error handling implemented
✅ Loading states implemented
✅ Success confirmations implemented

**Ready for backend integration!**

---

## 8. Task Streaming & Control (Task 12)

Use `/api/v1` prefixed endpoints for async agent orchestration.

### POST `/api/v1/agent/ask`
Queue a new agent task.

**Request Body:**
```json
{
  "query": "Analyze my dataset",
  "session_id": "optional-session-id",
  "file_id": "optional-file-id",
  "language": "fr"
}
```

**Response (202):**
```json
{
  "task_id": "uuid",
  "session_id": "string",
  "status": "queued",
  "message": "Requête en cours de traitement..."
}
```

### GET `/api/v1/agent/status/{task_id}`
Fallback polling endpoint.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "PENDING|STARTED|SUCCESS|FAILURE|CANCELED",
  "result": {},
  "error": "string",
  "cached": true,
  "payload": {}
}
```

### POST `/api/v1/agent/cancel/{task_id}`
Request cancel for running task.

**Response:**
```json
{
  "task_id": "uuid",
  "status": "canceled",
  "message": "Task cancellation requested."
}
```

### GET `/api/v1/agent/task/{task_id}/summary`
Single frontend-friendly summary endpoint (recommended).

**Response:**
```json
{
  "task_id": "uuid",
  "status": "started|pending|completed|failed|canceled",
  "terminal": false,
  "source": "celery|cache",
  "can_cancel": true,
  "result": {},
  "error": "string",
  "payload": {}
}
```

### GET `/api/v1/agent/history/cache?limit=20`
Returns recent terminal cached payloads for current user.

### WebSocket `/api/v1/ws/{task_id}?token={access_token}`
Real-time progress stream.

**Progress Payload Fields (important):**
- `status`: `started|processing|retrying|completed|failed|canceled`
- `type`: `started|processing|progress|result|error|heartbeat`
- `progress_percent`: `0..100`
- `eta_seconds`: integer or null
- `can_cancel`: boolean
- `reconnect_after_seconds`: integer (frontend reconnect hint)
- `emitted_at`: unix epoch seconds
- `token_count_input`, `token_count_output`, `token_count_total`

**Terminal Conditions:**
- Treat `completed`, `failed`, `canceled` as terminal.
- Also treat WebSocket close after terminal payload as normal.

### Frontend Handling Recommendation

1. Start with `POST /api/v1/agent/ask`.
2. Connect WebSocket immediately.
3. Update progress bar from `progress_percent`.
4. Show ETA using `eta_seconds` when available.
5. Enable/disable cancel button from `can_cancel`.
6. On reconnect, call `GET /api/v1/agent/task/{task_id}/summary` to recover state.
