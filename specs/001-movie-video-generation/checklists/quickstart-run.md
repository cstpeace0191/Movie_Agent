# Quickstart Run Verification Report

**Date**: 2026-11-20
**Provider**: `mock`
**Environment**: Python 3.11.9, Windows x86_64, Celery 5.5, MySQL / SQLite + SQLAlchemy 2.0, Redis

This document records the end-to-end verification of `specs/001-movie-video-generation/quickstart.md` using the mock engine.

---

## 1. Prerequisites & Health Check

- **FFmpeg & ffprobe**: Resolved via `imageio_ffmpeg` and system PATH. Subprocess execution flags include `-nostdin` and `-preset ultrafast`.
- **Redis & Celery**: Configured with solo pool on Windows, short connection timeouts in test mode.
- **GET /api/health**:
  - Response: `{"status": "ok", "provider": "mock", "queue": "ok"}`
  - Status code: `200 OK`
  - Auth required: No (public endpoint)

---

## 2. Authentication & CSRF (FR-030)

- **Registration**: `POST /api/auth/register` with `{"username": "demo_user", "password": "demo-password-123"}` -> `201 Created`
- **Login**: `POST /api/auth/login` -> `200 OK`, sets HttpOnly `movie_session` cookie and returns `csrf_token`.
- **CSRF Enforcement**: POST/DELETE requests without `X-CSRF-Token` header return `403 csrf_failed`.

---

## 3. User Story 1: Text Scenario to Video (P1)

- **Input**: 3-paragraph scenario.
- **Execution**:
  - `POST /api/jobs` returns `201 Created`, status `queued`.
  - Background worker splits text into 3 scenes (5.0s each).
  - Provider generates 3 video clips (`navy` color theme for text-only).
  - FFmpeg concat joiner combines shots into `final.mp4`.
  - Progress updates monotonically from 0% -> 10% -> 35% -> 60% -> 90% -> 100%.
- **Download**: `GET /api/jobs/{id}/video` returns valid MP4 of duration 15.0s.

---

## 4. User Story 2: Photos Only to Video (P1)

- **Input**: 3 JPEG/PNG photos with alt text.
- **Execution**:
  - `POST /api/jobs` validates magic bytes, dimensions, and size <= 20MB.
  - `input_mode` recorded as `IMAGE_ONLY`.
  - `DEFAULT_MOTION_PROMPT` assigned to each photo.
  - Video clips generated (`darkgreen` theme for image-to-video).
- **Download**: `GET /api/jobs/{id}/video` returns valid MP4.

---

## 5. User Story 3: Combined Scenario and Photos (P2)

- **Input**: 4 paragraphs with 2 photos.
- **Execution**:
  - Scene 1 mapped to Photo 1.
  - Scene 2 mapped to Photo 2.
  - Scenes 3 and 4 chained from the last frame of the preceding shot (`extract_last_frame`).
  - `unused_image_count`: 0.
- **Edge case**: 2 scenes with 3 photos -> `unused_image_count: 1`, job succeeds.

---

## 6. User Story 4: Progress Tracking & Retrieval (P2)

- **SSE Endpoint**: `GET /api/jobs/{id}/events` streams `progress` events and terminates on `done`.
- **List Jobs**: `GET /api/jobs` returns user's jobs sorted descending by `created_at`.
- **Isolation**: Another user accessing `/api/jobs/{id}` receives `404 not_found`.
- **Client UI**: React TypeScript SPA with semantic HTML5 landmarks, visible focus states, contrast ratio >= 4.5:1, keyboard operable.

---

## 7. User Story 5: Output Options (P3)

- **Options Tested**: `width=640`, `height=360`, `fps=12`, `seconds_per_shot=7.0`.
- **Output**: Downloaded video verified at 640x360 at 12 fps, shots scaled accordingly.
- **Validation**: `seconds_per_shot` outside 5–10s rejected with `422 validation_failed`.

---

## 8. User Story 6: Engine Choice & Cloud Disclosure (P2)

- **GET /api/providers**:
  - `ltx-2.3`: Local engine, default enabled.
  - `gemini-omni-1.2-flash`: Cloud engine, enabled if API key present, `sends_data_externally: true`.
  - `mock`: Dev engine, enabled in development/test.
- **Consent Gate**: Choosing cloud engine without `external_consent: true` returns `422 consent_required`.

---

## 9. Automated Check Results

```text
ruff check .           -> PASS (0 errors)
ruff format --check .  -> PASS (92 files formatted)
pytest tests/unit      -> PASS
pytest tests/contract  -> PASS
pytest tests/integration -> PASS
```

**Conclusion**: All Quickstart validation checks pass with zero deviations from specification.

