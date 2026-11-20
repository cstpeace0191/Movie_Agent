# Implementation Plan: Movie Video Generation from Scenario and Photos

**Branch**: `001-movie-video-generation` | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-movie-video-generation/spec.md`

## Summary

Build a client-server service where a logged-in user submits a text scenario, up to 100 photos, or both,
and receives one MP4 of at most 3 minutes. The server splits the scenario into scenes, maps photos to
scenes, generates one short shot per scene with a pluggable video engine, joins the shots into a final
MP4, streams progress to the browser, and deletes media 2 days after job creation.

Technical approach (details in [research.md](research.md)): FastAPI API with a React TypeScript client (built via Vite),
Celery + Redis for background generation with one job at a time per GPU, a `VideoProvider` abstraction
with a local LTX-2.3 default on an RTX 4090 (license and VRAM not yet verified; see Open Decisions), a Gemini Omni 1.2 Flash cloud option chosen per job, and a `mock` provider for development, FFmpeg for normalization and
joining, MySQL (with SQLite option) and local disk for the first release behind SQLAlchemy and a storage interface, and
Server-Sent Events for progress.

## Technical Context

**Language/Version**: Python 3.11 per spec.txt section 7. **Former conflict**: the scaffold's `.python-version`
and `pyproject.toml` specified 3.14. `pyproject.toml` now requires 3.11 or later (T001). `.python-version` still reads 3.14 and must change to 3.11 under T001. See Open Decisions.

**Primary Dependencies**: FastAPI, SQLAlchemy 2 (PyMySQL), Pydantic Settings, Celery 5, redis-py, google-genai (Gemini API), httpx (ComfyUI API for LTX-2.3 and
external API clients), argon2-cffi (password hashing), anthropic (scene splitting, optional), FFmpeg
(external binary, not a Python package).

**Storage**: MySQL 9.3 (production / compose) and SQLite (local testing) behind SQLAlchemy.
Local filesystem for photos, shots, and final videos (behind a storage interface, so MinIO/S3 is a later
adapter). Redis as the Celery broker and result backend.

**Testing**: pytest; `httpx` test client for API tests; contract test suite shared by every
`VideoProvider`; `axe-core` for accessibility scans of the client; `mock` provider for end-to-end tests
without a GPU.

**Target Platform**: Linux server with an NVIDIA GeForce RTX 4090 (24 GB VRAM) for local generation. Development on
Windows is supported (Celery runs with `--pool=solo`, per spec section 7).

**Project Type**: Web service (REST + SSE API, background worker) with a static browser client.

**Performance Goals** (budgets required by constitution Principle IV; proposed defaults, confirm against
the first benchmark):
- Non-generation API endpoints: p95 ≤ 300 ms at 5 concurrent users.
- Job submission acknowledgment: ≤ 1 s after the upload completes (SC-004).
- Progress visible to the user: updated at least every 10 s during generation (SC-003).
- Generation throughput: a 3-minute video (up to 36 shots) completes within 30 minutes on the RTX 4090 with LTX-2.3 (at risk; see Open Decisions 7)
  If the first benchmark cannot meet this, the 3-minute cap in FR-032 is revisited, not the budget
  silently relaxed.

**Constraints**:
- Generation: one job at a time per GPU (FR-026, `worker concurrency = 1`).
- Peak VRAM ≤ 24 GB on the RTX 4090. LTX-2.3 (22B) needs about 44 GB for bf16 weights alone, so an FP8 checkpoint or offloading is required (research VERIFY 2). The
  measured peak VRAM must stay within 24 GB at the chosen precision.
- Uploads: JPG/PNG/WebP, ≤ 20 MB per file, 1–100 photos per job (FR-003, FR-004).
- Finished video ≤ 3 minutes; shots 5–10 s each (FR-032, assumptions).
- Media deleted 2 days after job creation (FR-034).
- Secrets (API keys, session secret) only in `.env`, never committed (spec section 6).

**Scale/Scope**: ≤ 5 concurrent users (clarified). One GPU worker. Roughly 3 user-facing screens
(sign-in, job creation, job list/detail). 12 REST endpoints (contracts/rest-api.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | How this plan meets it | Status |
|------------------|------------------------|--------|
| I. Code Quality | `pyproject.toml` configures ruff (lint + format) and mypy for `server/` and `tests/`. Type annotations on all new code. Module boundaries follow the layout below (one responsibility per module). | PASS |
| II. Test-First (NON-NEGOTIABLE) | Tasks (next phase) will order each behavior as failing test → implementation. A shared contract test suite is required for each `VideoProvider`. Unit tests use fakes for LLM, engine, and FFmpeg; the real engine is only in a separate integration suite. | PASS (enforced in tasks) |
| III. Accessibility | Client is semantic HTML with labeled controls, keyboard-only flows, text errors, and an `aria-live` region for progress. `axe-core` runs in tests; manual keyboard and screen-reader pass before release. Captions are not required in this release because narration is out of scope. | PASS |
| IV. Performance | Budgets are stated in Technical Context. Generation runs as an async Celery job; the request handler never waits for generation. Model is loaded once per worker process. Retention sweep bounds disk use. | PASS |
| Technical constraint: engine behind `VideoProvider`, switched by env var | `VIDEO_PROVIDER` selects `ltx-2.3`, `gemini-omni-1.2-flash`, or `mock`. Each job may choose among the enabled providers in the UI (FR-035). No engine name appears outside `worker/providers/`. | PASS |
| Technical constraint: local open-weight default; restricted-license models not default | Default is LTX-2.3 (user choice). Its code is Apache 2.0, but the weights use a community license whose text could not be read. Adoption is blocked until the terms are confirmed, with Wan 2.2 (Apache 2.0) as the fallback. Gemini Omni is a cloud option, not a local default. HunyuanVideo is excluded (Korea restriction, spec section 2.1). | PENDING (blocks adoption, not planning) |
| Technical constraint: server owns generation | All generation happens in `server/worker`. Client only calls the REST and SSE API. | PASS |
| Development workflow: Constitution Check in plan | This table. | PASS |

**Result**: All planning gates pass. Two gates are PENDING: the LTX-2.3 weights license and the RTX 4090 VRAM check must pass before the local engine
is adopted (see Open Decisions 4). No exceptions need recording in Complexity Tracking.

**Post-design re-check (after Phase 1)**: Still passes, with the same engine gate pending. The design adds login (R10), which uses keyboard-only
sign-in in the client (Principle III, covered by the axe-core scan T051 and keyboard pass T058 in tasks.md). Retention
(R12) and the shot-retry contract (`ProviderError.transient`) support Principle IV's bounded resource use.
No new engine names appear outside `worker/providers/`.

## Open Decisions

These are decisions this plan makes by default. Confirm them before `/speckit-tasks`:

1. **Python version** (open until T001 is done): plan uses 3.11 (spec section 7). `pyproject.toml` requires 3.11 or later. `.python-version` still reads 3.14. Changing
   `.python-version` is part of T001 and still needs to change to 3.11.
2. **Scene splitting model** (resolved): `claude-haiku-5-5`, set by user decision on 2026-11-20. This replaces
   the spec section 7 choice of `claude-opus-5-5`. Output quality on sample scenarios must still be checked.
3. **Retention keeps job rows**: FR-034 deletes media. Plan keeps the job row with status `expired`, so the
   job list stays accurate. Confirm that is wanted.
4. **Local engine LTX-2.3 (BLOCKING ADOPTION)**: set by user decision on 2026-11-20, replacing Wan. Two checks
   are open. (a) The weights use the `ltx-2-community-license-agreement`, whose text could not be read; secondary
   sources cite a $10M revenue threshold, unverified. (b) On an RTX 4090 (24 GB), bf16 weights alone need about
   44 GB, so an FP8 checkpoint or offloading is required. If (a) fails, the default moves to Wan 2.2 (Apache 2.0).
   Planning and the mock-based tasks can proceed in the meantime. See research.md R1 and VERIFY items 1 and 2.
5. **Per-job engine choice and fallback**: the user asked for a UI choice between LTX-2.3 and Gemini Omni 1.2
   Flash, with Gemini used "when needed". This plan implements the per-job choice (FR-035). Automatic fallback
   to Gemini when the local engine fails or is busy is NOT built in this plan. Confirm whether you want it, and
   whether it should be on by default.
6. **Cloud engine data handling**: choosing Gemini Omni sends the scenario and photos to Google. FR-036 requires
   a disclosure and a confirmation per job. The cloud option stays disabled until Google's paid-tier retention and
   training terms are verified (research.md R15, VERIFY item 4).
7. **Performance budget at risk**: a secondary report puts LTX-2.3 at about 4 to 6 minutes per 10-second 1080p
   clip on an RTX 4090. At 36 shots, that exceeds the 30-minute budget. The budget must be measured at the spec
   default of 832×480 before it is treated as achievable (research.md VERIFY item 3).

## Project Structure

### Documentation (this feature)

```text
specs/001-movie-video-generation/
├── spec.md              # Feature specification (clarified)
├── plan.md              # This file
├── research.md          # Phase 0: decisions and alternatives
├── data-model.md        # Phase 1: entities, fields, states
├── quickstart.md        # Phase 1: run and validate end-to-end
├── contracts/
│   ├── rest-api.md      # Phase 1: HTTP and SSE contract
│   └── video-provider.md# Phase 1: engine interface contract
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 (/speckit-tasks), NOT created by this plan
```

### Source Code (repository root)

```text
pyproject.toml           # ruff, mypy, pytest configuration (existing file; extended in tasks)
docker-compose.yml       # Redis for development
server/
├── requirements.txt
├── .env.example
├── app/
│   ├── config.py        # Pydantic Settings (env-driven: VIDEO_PROVIDER, limits, secrets)
│   ├── db.py            # SQLAlchemy engine and session
│   ├── models.py        # ORM: User, Session, Job, Scene, Shot, SourceImage
│   ├── schemas.py       # Pydantic request/response models
│   ├── auth.py          # Password hashing, session cookies, CSRF check
│   ├── storage.py       # File storage interface (local implementation)
│   ├── api/
│   │   ├── auth.py      # /api/auth/*
│   │   └── jobs.py      # /api/jobs*, /api/health
│   └── main.py          # FastAPI app, static client mount
├── worker/
│   ├── celery_app.py    # Celery config, concurrency=1, retention beat schedule
│   ├── tasks.py         # run_job, run_shot, expire_old_jobs
│   ├── pipeline/
│   │   ├── split.py     # LLM split with paragraph fallback (F-03)
│   │   ├── mapping.py   # Photo-to-scene mapping and chain rules (F-04)
│   │   ├── frames.py    # Last-frame extraction for chained shots (FR-009)
│   │   ├── progress.py  # Writes progress to DB for SSE (F-07)
│   │   └── join.py      # FFmpeg normalize + concat → final.mp4 (F-06)
│   └── providers/
│       ├── base.py      # VideoProvider protocol and error types
│       ├── ltx.py       # LTX-2.3 local engine (ComfyUI API transport)
│       ├── mock.py      # FFmpeg-generated test clips (no GPU)
│       └── gemini.py    # Gemini Omni 1.2 Flash (cloud, chosen per job)
└── workflows/
    ├── ltx_t2v.json     # ComfyUI API-format template (LTX-2.3)
    └── ltx_i2v.json

client/
├── package.json         # Vite + React + TypeScript dependencies & scripts
├── vite.config.ts       # Vite configuration with /api proxy
├── tsconfig.json        # TypeScript configuration
├── index.html           # Semantic root markup & Vite module mount
├── style.css            # Accessible styles (focus indicators, >= 4.5:1 contrast)
└── src/
    ├── main.tsx         # React root mounting
    ├── App.tsx          # Main React UI component (auth, job form, SSE, table)
    ├── types.ts         # TypeScript interfaces for API models & events
    └── api.ts           # Typed API fetch helpers

tests/
├── contract/            # Shared VideoProvider contract suite (every provider runs it)
├── integration/         # API + worker with mock provider; LTX-2.3 test (GPU, optional)
└── unit/                # Splitting, mapping, validation, retention, auth
```

**Structure Decision**: Single Python project with a `server/` package (API and worker share models and
config) and a static `client/`. This matches spec section 8. The web app is served by the API, so there is
one deployable service plus Redis. Root-level `main.py` is an unused scaffold file; the tasks phase removes it.

## Complexity Tracking

> Constitution Check passed with no violations. Nothing to justify.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | | |
