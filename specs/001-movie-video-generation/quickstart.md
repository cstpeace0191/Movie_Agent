# Quickstart: Validate Movie Video Generation End-to-End

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **API**: [contracts/rest-api.md](contracts/rest-api.md)

This guide runs the whole flow with the `mock` video provider, so no GPU or ComfyUI is needed. It proves
each user story works. It does not describe implementation; that lives in `tasks.md`.

## Prerequisites

| Item | Check | Notes |
|------|-------|-------|
| Python | `python --version` | 3.11 per plan Open Decision 1 (confirm first) |
| FFmpeg and ffprobe | `ffmpeg -version`, `ffprobe -version` | Must be on `PATH` |
| Node.js & npm | `node --version`, `npm --version` | Node 18+ (for building React TypeScript client) |
| Docker (for Redis) | `docker --version` | Or any local Redis 7 server on port 6379 |
| curl | `curl --version` | Used for API checks below |

## Setup

```bash
cd "d:/CublickDigital-Codes/Movie_Agent"
python -m venv .venv
source .venv/Scripts/activate            # Windows Git Bash; use .venv/bin/activate on Linux
pip install -r server/requirements.txt
cp server/.env.example server/.env

# Build React TypeScript client
cd client && npm install && npm run build && cd ..
```

Edit `server/.env` and set:

```text
VIDEO_PROVIDER=mock
SESSION_SECRET=<any long random string for development>
ANTHROPIC_API_KEY=                       # leave empty: paragraph splitting is used
GEMINI_API_KEY=                          # leave empty: the cloud engine is shown as disabled
```

Start Redis:

```bash
docker compose up -d redis
```

## Run

Open three terminals from the repository root.

```bash
# 1. API server (serves the client at http://127.0.0.1:8000/)
fastapi dev --port 8000   # development: auto-reload; production uses `fastapi run`

# 2. Worker (one job at a time; --pool=solo is required on Windows)
celery -A server.worker.celery_app worker --pool=solo --concurrency=1 -l info

# 3. Scheduler (runs the retention sweep, FR-034)
celery -A server.worker.celery_app beat -l info
```

Health check (public, no login):

```bash
curl -s http://127.0.0.1:8000/api/health
# expected: {"status":"ok","provider":"mock","queue":"ok"}
```

## Validate: sign in

```bash
curl -s -c jar.txt -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"demo-password-123"}' \
  http://127.0.0.1:8000/api/auth/register

curl -s -c jar.txt -b jar.txt -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"demo-password-123"}' \
  http://127.0.0.1:8000/api/auth/login
# note the csrf_token in the response; use it as X-CSRF-Token below
```

Expected: login returns `csrf_token`. Any API call without the cookie returns `401 not_authenticated` (FR-030).

## Validate: User Story 1 (scenario only, P1)

```bash
CSRF="<csrf_token from login>"
curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" \
  -F "scenario=A fox wakes at dawn.

It walks to a quiet river.

The fox drinks, then looks at its reflection." \
  http://127.0.0.1:8000/api/jobs
```

Expected:
- `201` returned quickly with `"status":"queued"` and an `id` (SC-004).
- Watch progress: `curl -N -b jar.txt http://127.0.0.1:8000/api/jobs/<id>/events` shows `progress` events
  moving to 100 and a final `done` with `"status":"succeeded"` (SC-003).
- Download: `curl -s -b jar.txt -o out.mp4 http://127.0.0.1:8000/api/jobs/<id>/video`
- Check: `ffprobe -v error -show_entries format=duration -of csv=p=0 out.mp4` shows about 15 seconds
  (3 scenes × 5 seconds). Shot count from `GET /api/jobs/<id>` equals 3.

## Validate: User Story 2 (photos only, P1)

```bash
curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" \
  -F "images=@photo1.jpg" -F "images=@photo2.png" -F "images=@photo3.webp" \
  http://127.0.0.1:8000/api/jobs
```

Expected: `input_mode` is `IMAGE_ONLY`; shot count is 3; each shot's `source_image_id` is set (FR-011).

## Validate: User Story 3 (scenario and photos, P2)

Submit a four-paragraph scenario with two photos.

Expected:
- Photo 1 is used for scene 1, photo 2 for scene 2 (FR-008).
- Scenes 3 and 4 continue from the last frame of the previous shot when `chain_frames` is true (FR-009).
- With two photos and one fewer scene than photos, `unused_image_count` is 1 and the job still succeeds (FR-010).

## Validate: User Story 4 (progress and results, P2)

- Open `http://127.0.0.1:8000/` in a browser. Sign in with the keyboard only. Submit a job. Progress updates
  without a refresh (SC-005, FR-019).
- Log out and back in: the job list still shows the job (FR-020). Another user cannot see it (FR-031).

## Validate: User Story 5 (output options, P3)

```bash
curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" \
  -F "scenario=One short scene." -F "width=640" -F "height=360" \
  -F "seconds_per_shot=7" -F "fps=12" \
  http://127.0.0.1:8000/api/jobs
```

Expected: the downloaded MP4 is 640×360 at 12 fps (check with `ffprobe`), and each shot is 7 seconds within
1 second (FR-014).

## Validate: engine choice (FR-035, FR-036)

```bash
curl -s -b jar.txt http://127.0.0.1:8000/api/providers
# expected: ltx-2.3 is default and enabled; gemini-omni-1.2-flash is enabled: false
#           when GEMINI_API_KEY is empty, with a disabled_reason
curl -s -b jar.txt -H "X-CSRF-Token: $CSRF" -F "scenario=A short test." \
  -F "provider=gemini-omni-1.2-flash" http://127.0.0.1:8000/api/jobs
# expected without a key: 422 unknown_provider (not enabled)
# with a key but no external_consent=true: 422 consent_required
```

In the browser, the engine choice is a keyboard-operable radio group. LTX-2.3 is preselected. Choosing Gemini
shows the FR-036 text and a confirmation checkbox, and the Submit button stays disabled until it is checked.

## Validate: edge cases and limits

| Check | Request | Expected |
|-------|---------|----------|
| No input | no scenario, no images | `400 no_input` (FR-002) |
| Bad type | upload `notes.txt` renamed `.jpg` | `400 unsupported_file_type`, names the file |
| Too long | `seconds_per_shot=10` with 19 scenes | `422 too_long`, message states 180 s limit and planned length (FR-032) |
| Too many photos | 101 images | `400 too_many_images` (FR-004) |
| Another user's job | sign in as a second user and GET the first user's job | `404 not_found` (FR-031) |
| Video before done | download while `queued` | `409 not_ready` |
| Missing CSRF | POST without `X-CSRF-Token` | `403 csrf_failed` |

Shot failure and retry (FR-033) is tested with a `mock` setting that fails the first attempt: the shot is
retried once and the job succeeds. Two failures mark the job `failed` and name the shot (FR-027).

## Automated checks

```bash
ruff check . && ruff format --check .
mypy server tests
pytest tests/unit tests/contract -k mock
pytest tests/integration
```

Expected: all pass. Contract tests run against `mock`. The `ltx-2.3` contract tests require the RTX 4090 and are
skipped unless `LTX_COMFYUI_URL` is set. Gemini contract tests run only when `GEMINI_API_KEY` is set.

## Expected outcome summary

- Every user story passes its "Independent Test" in [spec.md](spec.md).
- Every edge case in the spec has a passing check above or in the integration suite.
- Constitution gates: lint and type checks pass; contract tests pass for every provider that is enabled.
