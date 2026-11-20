# Contract: REST and SSE API v1

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Data**: [data-model.md](../data-model.md)

This replaces the spec section 5 sketch. It adds authentication (FR-030), ownership (FR-031), and the
retention status (FR-034). Base path: `/api`. Format: JSON unless noted.

## Conventions

- **Authentication**: all endpoints except `POST /api/auth/register`, `POST /api/auth/login`, and
  `GET /api/health` require a valid session cookie (`movie_session`, HttpOnly, SameSite=Lax).
- **CSRF**: `POST` and `DELETE` requests require header `X-CSRF-Token` matching the session's CSRF token,
  returned by `POST /api/auth/login` and `GET /api/auth/me`.
- **Errors**: every error has the shape `{"error": {"code": "<machine_code>", "message": "<plain language>"}}`.
  Messages are text only and never depend on color (FR-029).
- **Ownership**: a resource owned by another user returns `404 not_found`, identical to a missing resource
  (FR-031).
- **Timestamps**: ISO 8601 UTC.

## Authentication

### POST /api/auth/register

Request: `{"username": "string", "password": "string"}`. Password minimum 12 characters (proposed default).

- `201`: `{"id", "username"}`. Does not log the user in.
- `409 username_taken`
- `422 validation_failed` (username or password rule violated; message names the rule)

### POST /api/auth/login

Request: `{"username", "password"}`.

- `200`: `{"id", "username", "csrf_token"}` and sets the `movie_session` cookie.
- `401 invalid_credentials` (same message for unknown user and wrong password)

### POST /api/auth/logout

- `204`. Invalidates the session. Requires CSRF header.

### GET /api/auth/me

- `200`: `{"id", "username", "csrf_token"}`
- `401 not_authenticated`

## Engines

### GET /api/providers

Authenticated. Lists the engines the user can choose for a job (FR-035). The UI builds its engine choice
from this list, so the list is the only source of engine names the front end uses.

- `200`:
  ```json
  [
    {"id": "ltx-2.3", "label": "LTX-2.3 (local GPU, default)", "location": "local",
     "enabled": true, "is_default": true, "sends_data_externally": false,
     "max_clip_seconds": null, "disabled_reason": null},
    {"id": "gemini-omni-1.2-flash", "label": "Gemini Omni 1.2 Flash (cloud)", "location": "cloud",
     "enabled": false, "is_default": false, "sends_data_externally": true,
     "max_clip_seconds": 15, "disabled_reason": "Cloud engine is not configured on this server."}
  ]
  ```
- `enabled` is `false` with a `disabled_reason` when the engine is not configured (for example, no Gemini key).
- `mock` appears only in development mode.
- `sends_data_externally: true` makes the UI show the FR-036 disclosure before submission.

## Jobs

### POST /api/jobs

`multipart/form-data`. Requires CSRF header.

| Part | Type | Default | Rule |
|------|------|---------|------|
| scenario | string | none | Optional. Trimmed; empty string counts as absent. |
| images | file[] | none | Optional. 1–100 files (FR-004). jpg/png/webp, ≤ 20 MB each (FR-003). |
| width | int | 832 | Positive; engine constraints per research VERIFY item 6 |
| height | int | 480 | Positive |
| seconds_per_shot | float | 5 | 5–10 |
| fps | int | 16 | Positive |
| provider | string | server default | One of `ltx-2.3`, `gemini-omni-1.2-flash`, `mock`. Must be enabled (see `GET /api/providers`). |
| chain_frames | bool | true | |
| external_consent | bool | false | Must be `true` when the provider is a cloud engine (FR-036). Ignored for local engines. |
| image_alt_texts | string (JSON array) | none | Optional. Entry i is the alt text for `images[i]`. Each entry ≤ 500 chars (FR-037, constitution III). |

- `201`:
  ```json
  {"id": "uuid", "status": "queued", "input_mode": "TEXT_IMAGE", "progress": 0,
   "message": "Queued", "unused_image_count": 0, "planned_seconds": 15.0,
   "expires_at": "2026-11-22T10:00:00Z"}
  ```
  Returns immediately after enqueueing (FR-024, SC-004).
- `400 no_input` when neither scenario nor images are given (FR-002)
- `400 too_many_images` (more than 100)
- `400 unsupported_file_type` (`message` names the file; other files are not affected)
- `413 file_too_large` (`message` states the 20 MB limit)
- `422 too_long` when `planned_seconds > 180` (FR-032). Message states the limit and planned length.
- `422 unknown_provider` (not known, or known but not enabled)
- `422 consent_required` when a cloud provider is chosen and `external_consent` is not `true` (FR-036)
- `403 csrf_failed` when the CSRF header is missing or wrong

### GET /api/jobs

Returns the caller's jobs only, most recent first (FR-023).

- `200`: `[JobSummary]`. `JobSummary` is `Job` without `shots`.

### GET /api/jobs/{id}

- `200`: `Job`
  ```json
  {"id", "status", "input_mode", "progress", "message", "failure_reason",
   "options": {"width", "height", "seconds_per_shot", "fps", "chain_frames", "provider"},
   "planned_seconds", "unused_image_count", "created_at", "updated_at", "expires_at",
   "shots": [{"position", "status", "attempts", "scene_excerpt", "source_image_id", "error"}],
   "video_url": "/api/jobs/{id}/video or null"}
  ```
  `scene_excerpt` is the first 120 characters of the scene description (FR-022).
- `404 not_found`

### GET /api/jobs/{id}/events

Server-Sent Events (`text/event-stream`). Requires the session cookie (EventSource sends it automatically
for same-origin requests).

Events:
- `event: progress`, `data:` the same object as `GET /api/jobs/{id}` minus `shots`. Sent on every change to
  status, progress, or message, and at least every 10 seconds as a heartbeat (SC-003).
- `event: shot`, `data:` one shot object. Sent when a shot changes state (FR-022).
- `event: done`, `data:` `{"status": "succeeded" | "failed" | "expired"}`. Closes the stream.

If the job is already finished when the client connects, the server sends the current state followed by
`done`. A reconnecting client receives the current state first (FR-020).

- `404 not_found`

### GET /api/jobs/{id}/video

- `200` `video/mp4` with `Content-Disposition: attachment; filename="movie-{id}.mp4"`. Supports HTTP Range
  requests for playback.
- `409 not_ready` when status is `queued` or `running`: "The video is not ready yet." (spec edge case)
- `409 failed` when status is `failed`
- `404 not_found` when missing, owned by another user, or `expired` (FR-034)

### DELETE /api/jobs/{id}

Deletes the job's media now, before the retention deadline. Requires CSRF header.

- `204`
- `404 not_found`
- `409 job_running` when status is `queued` or `running`. Cancellation is not in this release.

## Health

### GET /api/health

Public. No user data.

- `200`: `{"status": "ok", "provider": "mock", "queue": "ok" | "unavailable"}`

## Client Application

`GET /` and static assets serve the built React TypeScript application from `client/dist/` (or `client/`). These are not part of the API contract.
