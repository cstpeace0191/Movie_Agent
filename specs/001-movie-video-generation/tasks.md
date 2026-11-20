# Tasks: Movie Video Generation from Scenario and Photos

**Input**: Design documents from `specs/001-movie-video-generation/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The template makes tests optional, but constitution Principle II (Test-First,
NON-NEGOTIABLE) requires them. Each test is written first and must FAIL before its implementation task starts.

**Organization**: Grouped by user story (spec.md priorities P1 to P3). Phase 8 is User Story 6 (engine choice).
Phases 9 and 10 hold work that is not a user story (local engine, retention). Those phases carry no `[Story]` label, per the format rules.

**Approval**: Task list approved by the user on 2026-11-20. Scope: the tasks listed in this file as of that date.
Implementation has not started. Gates still open: T072 (LTX-2.3 license) and T073 (RTX 4090 VRAM and precision).

**Remediation (2026-11-20)**: Fixes approved from `/speckit-analyze` for C1, C2, C3, C4, C5, I1, S1, G1, A3, and I3. The spec gained FR-037 and User Story 6. Tasks T026, T028, T033, T055, T057, T063, T067, T070, T074, T075, T086, and T090 were amended. T091 to T093 were added. Phase 8 is relabeled as User Story 6.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US6 for user story phases only
- Paths are relative to the repository root

## Path Conventions

Layout from plan.md "Source Code". Two additions are flagged where they appear:
`server/worker/pipeline/frames.py` (T046) and `server/app/api/` routes live in `jobs.py` and `auth.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and tooling

- [x] T001 Set `.python-version` to 3.11 to match `requires-python` (>=3.11) in `pyproject.toml`. The 3.11 decision is recorded in plan.md Open Decision 1.
- [x] T002 Remove the unused scaffold file `main.py` at the repository root (plan Structure Decision).
- [x] T003 Create the directory skeleton with `__init__.py` files: `server/app/api/`, `server/worker/pipeline/`, `server/worker/providers/`, `server/workflows/`, `client/`, `tests/contract/`, `tests/integration/`, `tests/unit/`.
- [x] T004 Extend `pyproject.toml` with ruff (lint and format), mypy (targets `server` and `tests`), and pytest configuration, per constitution Principle I.
- [x] T005 [P] Create `server/requirements.txt` pinning `fastapi[standard]` (the FastAPI CLI and its uvicorn server, per the FastAPI deployment docs), SQLAlchemy 2, Pydantic Settings, Celery 5, redis, httpx, argon2-cffi, anthropic, google-genai, pytest, ruff, mypy, and playwright (for the accessibility test). Do not add a separate `uvicorn` line.
- [x] T006 [P] Create `server/.env.example` listing `VIDEO_PROVIDER`, `SESSION_SECRET`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `LTX_COMFYUI_URL`, `REDIS_URL`, `DATABASE_URL`, and `STORAGE_DIR`, with empty values and comments.
- [x] T007 [P] Create `docker-compose.yml` at the repository root with one `redis` service (Redis 7, port 6379).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that every user story needs. No user story work begins until this phase is complete.

**CRITICAL**: Login (FR-030), the data model, the provider contract, and the worker must exist first.

- [x] T008 [P] Write the shared provider contract suite in `tests/contract/test_provider_contract.py`, parametrized over provider names. It covers every row of the "Contract tests" table in `contracts/video-provider.md`. Run it now and confirm it FAILS (no provider exists yet).
- [x] T009 [P] Write `tests/unit/test_config.py`: `VIDEO_PROVIDER` accepts only `ltx-2.3`, `gemini-omni-1.2-flash`, and `mock`; defaults are 100 images, 20 MiB per image, 180 planned seconds, a 2-day retention, and a 7-day session lifetime. Confirm FAIL.
- [x] T010 Implement `server/app/config.py` with Pydantic Settings. It reads the variables from `server/.env.example`, validates `VIDEO_PROVIDER` against the three names, and holds the limit constants. Depends on T009.
- [x] T011 [P] Implement `server/app/db.py`: SQLAlchemy engine and session factory from `DATABASE_URL`, supporting MySQL (PyMySQL) and SQLite fallback. No module-level mutable state.
- [x] T012 Implement the `User` and `Session` ORM models in `server/app/models.py`, with these constraints from data-model.md (tests first: T097):
  - `User.username`: "Unique, 3–32 chars, letters/digits/underscore, case-insensitive uniqueness"
  - `User.password_hash`: "argon2id hash; never returned by any API"
  - `Session.token_hash`: "SHA-256 of the random session token; the raw token is only in the cookie"
  - `Session.csrf_token`: "Random; required in a header for POST and DELETE"
  - `Session.last_seen_at`: "Updated on use; session expires 7 days after this"
- [x] T013 Implement the `Job`, `Scene`, `Shot`, and `SourceImage` ORM models in `server/app/models.py`, with these constraints from data-model.md (tests first: T097):
  - `Job.owner_id`: "required; every query filters on it (FR-031)"
  - `Job.status`: "queued, running, succeeded, failed, expired"
  - `Job.progress`: "0–100 inclusive (FR-018)"
  - `Job.seconds_per_shot`: "Range 5–10 (spec assumptions)"
  - `Job.planned_seconds`: "Derived: shot count × seconds_per_shot. Must be ≤ 180 (FR-032)"
  - `Job.expires_at`: "created_at + 2 days (FR-034)"
  - `Scene.position`: "0-based, unique within the job, contiguous (FR-005)"
  - `Shot.attempts`: "0–2. Retry allowed once (FR-033)"
  - `SourceImage.media_type`: "image/jpeg, image/png, image/webp (FR-003)"
  - `SourceImage.size_bytes`: "≤ 20 × 1024 × 1024 (FR-003)"
  - `SourceImage.alt_text`: "Optional, ≤ 500 chars (constitution Principle III)"
  - `SourceImage.storage_path`: "Server-generated path; never derived from the filename"
- [x] T014 [P] Implement `server/app/schemas.py`: Pydantic models for the job create options, `JobOut`, `ShotOut`, the `ProviderOut` list item, and the error body `{"error": {"code", "message"}}` from `contracts/rest-api.md`.
- [x] T015 Write `tests/integration/test_auth.py`: register, then login, then `/api/auth/me`. Unauthenticated calls return `401 not_authenticated` (FR-030). A POST without the CSRF header returns `403 csrf_failed`. An unknown user and a wrong password return the same `401 invalid_credentials` message. Confirm FAIL.
- [x] T016 Implement `server/app/auth.py`: argon2id hashing, session creation and lookup by SHA-256 token hash, a `require_user` dependency, and the CSRF check for POST and DELETE (research R10). Depends on T012, T015.
- [x] T017 Implement the `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, and `/api/auth/me` routes in `server/app/api/auth.py` per `contracts/rest-api.md`. Depends on T016.
- [x] T018 Implement `server/app/main.py`: FastAPI app, a global exception handler that returns the `{"error": {"code", "message"}}` shape, a static mount of `client/` at `/`, the auth router, and `GET /api/health` returning `{status, provider, queue}`. Depends on T010, T017, T096 (tests first).
- [x] T019 [P] Implement `server/app/storage.py` (local disk): paths are built from job and image IDs under `STORAGE_DIR`. The uploaded filename is never used as a path. Add `delete_job_media(job_id)` for retention (FR-034).
- [x] T020 Implement `server/worker/providers/base.py`: the `VideoProvider` protocol, `ShotRequest`, `ShotResult`, and `ProviderError` with a `transient` flag, exactly as in `contracts/video-provider.md`.
- [x] T021 Implement `server/worker/providers/mock.py`: FFmpeg-generated clips (solid color with the shot number as text) for T2V and I2V. It supports failure injection through `MOCK_FAIL_SHOTS` (for example `2:1` fails shot 2 on its first attempt) for the FR-033 tests. It is enabled only in development mode. Depends on T008, T020. Confirm the contract suite now PASSES for `mock`.
- [x] T022 Implement `server/worker/celery_app.py`: Celery 5 app from `REDIS_URL`, `worker_concurrency=1` (FR-026), a per-task time limit read from config (FR-025), and an empty beat schedule that T083 fills in. Depends on T010.

**Checkpoint**: Foundation ready. Login, the data model, the provider contract, and the worker exist. User stories can start.

---

## Phase 3: User Story 1 - Create a Video from a Text Scenario (Priority: P1) MVP

**Goal**: A logged-in user submits a scenario only and receives a finished MP4 with one shot per scene.

**Independent Test**: Submit a 3-paragraph scenario through the API with the `mock` provider. The job reaches `succeeded`, has 3 shots, and the downloaded MP4 is about 15 seconds long (quickstart "User Story 1").

### Tests for User Story 1 (write first, confirm FAIL)

- [x] T023 [P] [US1] Write `tests/unit/test_split_paragraph.py`: the paragraph splitter keeps every non-empty paragraph, in order, with no loss (FR-005, FR-007).
- [x] T024 [P] [US1] Write `tests/unit/test_split_llm.py`: with a fake LLM client, invalid JSON, a missing key, or a duration outside 5–10 s falls back to the paragraph split (FR-006). Check that the call uses model `claude-haiku-5-5` (research R6).
- [x] T025 [P] [US1] Write `tests/unit/test_job_validation.py`: no scenario and no images returns `400 no_input` (FR-002). A planned length over 180 seconds returns `422 too_long`, and the message states the limit and the planned length (FR-032).
- [x] T026 [P] [US1] Write `tests/integration/test_scenario_job.py`: `POST /api/jobs` with a scenario only returns `201` with `status: queued` in under 1 second (SC-004). The job then reaches `succeeded` with the mock provider, the shot count equals the scene count, and the MP4 downloads. The job detail lists one shot per scene with its status (FR-022).
- [x] T027 [P] [US1] Write `tests/integration/test_shot_retry.py`: with `MOCK_FAIL_SHOTS=2:1`, shot 2 is retried once and the job succeeds. With `MOCK_FAIL_SHOTS=2:2`, the job is `failed` and `failure_reason` names shot 2 (FR-033, FR-027).

### Implementation for User Story 1

- [x] T028 [US1] Implement `server/worker/pipeline/split.py`: a paragraph splitter and an LLM splitter (`claude-haiku-5-5` through the anthropic SDK). The LLM output is validated (`prompt`, `duration`); narration is out of scope for this release (spec Assumptions), and any failure falls back to the paragraph split. Depends on T023, T024.
- [x] T029 [US1] Implement the scenario-only path of `POST /api/jobs` in `server/app/api/jobs.py`. It validates the input (T025), creates the `Job` and `Scene` rows, sets each scene's duration to the splitter's duration when it is within 5–10 s and to `seconds_per_shot` otherwise (data-model Scene.duration), returns `201` per the contract, and enqueues `run_job`. Depends on T013, T016, T028.
- [x] T030 [P] [US1] Implement `server/worker/pipeline/progress.py`: writes `status`, `progress`, and `message` to the `Job` row at each stage and shot change (FR-018, research R5). Depends on T098 (tests first).
- [x] T031 [US1] Implement `run_job` in `server/worker/tasks.py`. It sets `running`, generates the shots in order through the provider from config, retries a failed shot once (FR-033), marks the job `failed` with the shot named if the retry also fails, and calls `join`. Depends on T020, T021, T030.
- [x] T032 [US1] Implement `server/worker/pipeline/join.py`: normalizes every shot to the job's width, height, and fps, then concatenates them into `final.mp4` with FFmpeg. Use argument lists only, never shell strings (research R8). Depends on T021.
- [x] T033 [US1] Implement `GET /api/jobs/{id}` and `GET /api/jobs/{id}/video` in `server/app/api/jobs.py`. They filter on the owner (other users get `404 not_found`), return `409 not_ready` or `409 failed` as the contract states, support HTTP Range requests, and include the `shots` array in `GET /api/jobs/{id}` (position, status, attempts, scene excerpt, source image id, error) per `contracts/rest-api.md` (FR-022). Depends on T029, T032.

**Checkpoint**: User Story 1 works independently through the API.

---

## Phase 4: User Story 2 - Create a Video from Photos Only (Priority: P1)

**Goal**: A logged-in user uploads 1 to 100 photos with no scenario and gets one shot per photo.

**Independent Test**: Upload 3 photos with no scenario. The job runs in `IMAGE_ONLY` mode with 3 shots, and each shot links to its photo.

### Tests for User Story 2 (write first, confirm FAIL)

- [x] T034 [P] [US2] Write `tests/unit/test_upload_validation.py`: a file is accepted by its magic bytes (not its extension) if it is JPG, PNG, or WebP. Other types return `400 unsupported_file_type` and the message names the file. Over 20 MiB returns `413 file_too_large`. A 101st photo returns `400 too_many_images` (FR-003, FR-004).
- [x] T035 [P] [US2] Write `tests/unit/test_mapping_photo_only.py`: 3 photos give 3 shots, shot i uses photo i, and the default motion prompt is used (FR-011).
- [x] T036 [P] [US2] Write `tests/integration/test_photo_job.py`: `POST /api/jobs` with 3 images returns `input_mode: IMAGE_ONLY`. The job succeeds with 3 shots, and each shot has a `source_image_id` (User Story 2 scenarios 1 and 2). It also sends `image_alt_texts`, checks that each alt text is stored on its photo, and checks that a 501-character alt text is rejected with `422 validation_failed` (FR-037).

### Implementation for User Story 2

- [x] T037 [US2] Add upload validation to `server/app/storage.py`: magic-byte check, size limit, count limit, and a sanitized original filename kept for display only (T034). Depends on T019, T034.
- [x] T038 [US2] Implement the photo-only mapping and the default motion prompt constant in `server/worker/pipeline/mapping.py` (FR-011). Depends on T035.
- [x] T039 [US2] Extend `POST /api/jobs` in `server/app/api/jobs.py` to accept `images` parts and the `image_alt_texts` array, save `SourceImage` rows (`position`, `media_type`, `size_bytes`, `storage_path`, optional `alt_text`), and set `input_mode` to `IMAGE_ONLY`. Depends on T029, T037, T038.
- [x] T040 [US2] Extend `run_job` in `server/worker/tasks.py` so photo shots use image-to-video, passing the photo as `source_image_path`. Depends on T031, T039.

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Create a Video from Both Scenario and Photos (Priority: P2)

**Goal**: A logged-in user supplies a scenario and photos together. Each photo matches a scene, and extra scenes continue from the previous shot.

**Independent Test**: A 4-paragraph scenario with 2 photos. Scene 1 uses photo 1, scene 2 uses photo 2, and scenes 3 and 4 continue from the previous shot's last frame.

### Tests for User Story 3 (write first, confirm FAIL)

- [x] T041 [P] [US3] Write `tests/unit/test_mapping_combined.py`: photo n maps to scene n (FR-008). Extra scenes reuse the last photo or the previous last frame (FR-009). Extra photos set `unused_image_count` and `used: false` (FR-010).
- [x] T042 [P] [US3] Write `tests/unit/test_last_frame.py`: last-frame extraction returns an image whose size equals the shot's width and height.
- [x] T043 [P] [US3] Write `tests/integration/test_combined_job.py`: 4 paragraphs with 2 photos. The job succeeds, scene 1 uses photo 1, scene 2 uses photo 2, and scenes 3 and 4 are chained (`chain_frames` true).
- [x] T044 [P] [US3] Write `tests/integration/test_combined_unused.py`: 2 scenes with 3 photos gives `unused_image_count: 1`, and the job still succeeds (FR-010).

### Implementation for User Story 3

- [x] T045 [US3] Extend `server/worker/pipeline/mapping.py` with combined-mode mapping and the chain rules (FR-008 to FR-010, FR-015). Depends on T038, T041.
- [x] T046 [US3] Create `server/worker/pipeline/frames.py`, which extracts the last frame of a clip with FFmpeg. This module is not in the plan's file list; it is added here as the smallest unit for T042. Depends on T042.
- [x] T047 [US3] Wire `chain_frames` into `run_job`: the previous shot's last frame becomes the next shot's source image, and `SourceImage.used` is set correctly. Depends on T040, T045, T046.

**Checkpoint**: User Stories 1 to 3 work independently.

---

## Phase 6: User Story 4 - Track Progress and Retrieve Results (Priority: P2)

**Goal**: A user sees live progress, can list their jobs, and downloads results. The browser client is fully keyboard-operable.

**Independent Test**: Submit a job and keep the page open. Progress reaches 100 without a refresh. The finished job appears in the list with a download action. A failed job shows a plain-language reason.

### Tests for User Story 4 (write first, confirm FAIL)

- [x] T048 [P] [US4] Write `tests/integration/test_sse_events.py`: the `/api/jobs/{id}/events` stream sends `progress` events, a heartbeat at least every 10 seconds (SC-003), `shot` events, and a final `done` event (FR-019, FR-022).
- [x] T049 [P] [US4] Write `tests/integration/test_job_list.py`: `GET /api/jobs` returns only the caller's jobs, most recent first (FR-023, FR-031). Another user's job returns `404`, the same as a missing job.
- [x] T050 [P] [US4] Write `tests/integration/test_reconnect.py`: a client that connects after the job finished receives the current state, then `done` (FR-020).
- [x] T051 [P] [US4] Write `tests/integration/test_a11y.py`: an axe-core scan of the sign-in page, the job form, and the job list reports no serious or critical violations. Every control is reachable by keyboard (constitution Principle III, SC-005). Every error shown on these pages is text, not color alone (FR-029).

### Implementation for User Story 4

- [x] T052 [US4] Implement `GET /api/jobs` in `server/app/api/jobs.py`: owner filter, most recent first, `JobSummary` shape (contract). Depends on T033, T049.
- [x] T053 [US4] Implement `GET /api/jobs/{id}/events` in `server/app/api/jobs.py` as SSE. It reads progress from the database, sends a heartbeat at least every 10 seconds, and is safe to reconnect (research R5). Depends on T030, T048, T050.
- [x] T054 [US4] Implement `DELETE /api/jobs/{id}` in `server/app/api/jobs.py`: CSRF check, `409 job_running` for a queued or running job, and immediate deletion of the job's media through `storage.delete_job_media` (FR-038). Depends on T019, T052, T095 (tests first).
- [x] T055 [P] [US4] Write `client/index.html` with semantic structure: a sign-in form, a registration form (username and password), a logout control, a job form (a labeled scenario textarea, a labeled file input, and one labeled, optional alt-text field per selected photo, max 500 characters, FR-037), a job list table, an `aria-live="polite"` progress region, and a `role="alert"` error region.
- [x] T056 [P] [US4] Write `client/style.css`: visible focus styles, text contrast of at least 4.5:1, and UI boundary contrast of at least 3:1 (constitution Principle III). After this change, run the T051 axe scan and a keyboard pass.
- [x] T057 [US4] Write React TypeScript client (`client/src/App.tsx`, `client/src/main.tsx`, `client/src/api.ts`): `fetch` calls for register, login, and logout (sending `X-CSRF-Token` where required), an `EventSource` that updates the progress region, a job list and detail view, a download link shown only when the job succeeds, and `409` messages shown as text. It sends each photo's alt text with the job (FR-037). Depends on T052, T053, T055.
- [x] T058 [US4] Perform a keyboard-only manual pass of the full flow and record the result in `specs/001-movie-video-generation/checklists/a11y-manual.md` (constitution Principle III requires a manual pass before release). Depends on T057.

**Checkpoint**: User Stories 1 to 4 work. The UI is usable from the browser.

---

## Phase 7: User Story 5 - Adjust Output Options (Priority: P3)

**Goal**: A user can set resolution, seconds per shot, fps, and chain_frames. Defaults apply when they are not set.

**Independent Test**: Submit one scenario with 640×360, 7-second shots, and 12 fps. The downloaded MP4 matches those settings within tolerance.

### Tests for User Story 5 (write first, confirm FAIL)

- [x] T059 [P] [US5] Write `tests/unit/test_options.py`: defaults are 832×480, 5 s, 16 fps, and `chain_frames` true. `seconds_per_shot` outside 5–10 returns `422 validation_failed` with a plain-language message. fps must be positive.
- [x] T060 [P] [US5] Write `tests/integration/test_options_job.py`: 640×360 at 12 fps with 7-second shots produces an MP4 at that resolution and fps, and each shot is within 1 second of 7 seconds (User Story 5 scenario 2).

### Implementation for User Story 5

- [x] T061 [US5] Implement option parsing and validation in `server/app/api/jobs.py` and `server/app/schemas.py` (width, height, fps, seconds_per_shot 5–10, chain_frames). Depends on T029, T059.
- [x] T062 [US5] Pass the job's width, height, and fps options from `POST /api/jobs` into the join step, so `server/worker/pipeline/join.py` (T032) normalizes to the requested values. Add no new normalization logic (FR-013). Depends on T032, T060.
- [x] T063 [US5] Add labeled option controls with defaults to `client/src/App.tsx` and `client/index.html` (FR-014). After this change, run the T051 axe scan and a keyboard pass, and record the result in `checklists/a11y-manual.md` (constitution III). Depends on T057.

**Checkpoint**: All five user stories work independently.

---

## Phase 8: User Story 6 - Choose a Video Engine per Job (Priority: P2)

**Purpose**: Let the user pick LTX-2.3 or Gemini Omni 1.2 Flash for each job, with a disclosure before any data goes to Google.

**Story**: User Story 6 in spec.md covers FR-035 and FR-036 (added by remediation).

### Tests (write first, confirm FAIL)

- [x] T064 [P] [US6] Extend `tests/contract/test_provider_contract.py` with `gemini-omni-1.2-flash`. It is skipped unless `GEMINI_API_KEY` is set, and it runs only when triggered manually, because each run costs money.
- [x] T065 [P] [US6] Write `tests/integration/test_engine_list.py`: `GET /api/providers` returns `ltx-2.3` as default and enabled. `gemini-omni-1.2-flash` is `enabled: false` with a `disabled_reason` when no key is set. `mock` appears only in development mode.
- [x] T066 [P] [US6] Write `tests/integration/test_consent.py`: a cloud provider without `external_consent: true` returns `422 consent_required`. With consent, `external_consent_at` is recorded, and no provider call happens before the consent is recorded (contract rule 6).

### Implementation

- [x] T067 [US6] Implement `server/worker/providers/gemini.py`: the Gemini API via google-genai, model `gemini-omni-1.2-flash`, a 15-second maximum clip check (contract rule 7), a refusal to run without recorded consent (contract rule 6), and a mapping of API errors to `ProviderError.transient`. BLOCKED: do not implement until Google's paid-tier retention and training terms are verified (research VERIFY item 4). Depends on T020, T064.
- [x] T068 [US6] Implement `GET /api/providers` in `server/app/api/jobs.py` with the response shape in `contracts/rest-api.md`. Depends on T065.
- [x] T069 [US6] Add consent handling to `POST /api/jobs`: `422 consent_required`, and set `Job.external_consent_at`. Depends on T029, T066.
- [x] T070 [US6] Add the engine radio group to `client/src/App.tsx` and `client/index.html`. LTX-2.3 is preselected. Choosing Gemini shows the FR-036 text and a confirmation checkbox, and the submit button stays disabled until the box is checked. The group is keyboard-operable with arrow keys. After this change, run the T051 axe scan and a keyboard pass (constitution III). Depends on T057, T068.
- [x] T071 [US6] Implement the provider registry: a job's `provider` resolves to a `VideoProvider` in one place. No engine name appears outside `server/worker/providers/` (FR-016). Depends on T021, T067.

---

## Phase 9: Local Engine LTX-2.3 (default) - no user story label

**Purpose**: The production local engine on the RTX 4090.

**BLOCKED**: T072 and T073 must pass before any other task in this phase starts (research VERIFY items 1 and 2).

- [ ] T072 BLOCKED: verify the LTX-2.3 weights license (`ltx-2-community-license-agreement`), including revenue thresholds, enterprise terms, and any territorial restriction (Korea). If it does not pass, switch the default to Wan 2.2 and record the decision in plan.md Open Decisions 4.
- [ ] T073 BLOCKED: verify an FP8 checkpoint or an offloading path for the RTX 4090 (24 GB). Measure peak VRAM at 832×480, 16 fps, 5-second shots. Record the result in research.md.
- [x] T074 [P] Write `tests/integration/test_ltx_gpu.py`: the shared contract suite runs against `ltx-2.3`. It is skipped unless `LTX_COMFYUI_URL` is set, and it is a GPU-gated job. It asserts that two consecutive shots reuse one engine load (constitution IV).
- [x] T075 Implement `server/worker/providers/ltx.py`: the ComfyUI API client (submit workflow, poll, fetch the clip) for both T2V and I2V. Load the engine client once per worker process and reuse it across jobs (constitution IV); T074 asserts this. Depends on T020, T072, T073, T074.
- [x] T076 [P] Create `server/workflows/ltx_t2v.json` in ComfyUI API format (research VERIFY item 5).
- [x] T077 [P] Create `server/workflows/ltx_i2v.json` in ComfyUI API format (research VERIFY item 5).
- [x] T078 Register `ltx-2.3` as the default provider and set it in the `VIDEO_PROVIDER` default. Depends on T071, T075.
- [ ] T079 Benchmark a 36-shot (3-minute) job on the RTX 4090 at 832×480. Record the time in plan.md Performance Goals and resolve Open Decision 7 (research VERIFY item 3). Depends on T078.

---

## Phase 10: Retention and Operations (FR-025, FR-026, FR-034) - no user story label

**Purpose**: Automatic deletion, time limits, and queue behavior.

### Tests (write first, confirm FAIL)

- [x] T080 [P] Write `tests/unit/test_retention.py`: a job older than 2 days has its media deleted, its status is `expired`, its row is kept, and its download returns `404` (FR-034, research R12).
- [x] T081 [P] Write `tests/integration/test_time_limit.py`: a job over the time limit is marked `failed` with a timeout message, and the next queued job still runs (FR-025).
- [x] T082 [P] Write `tests/integration/test_queue_order.py`: two queued jobs run one at a time, in order. The waiting job shows `queued` (FR-026).

### Implementation

- [x] T083 Implement `expire_old_jobs` in `server/worker/tasks.py` and add an hourly beat entry in `server/worker/celery_app.py` (research R12). Depends on T019, T080.
- [x] T084 Implement the per-task time limit and the timeout failure message in `run_job` (FR-025). Depends on T031, T081.
- [x] T085 Confirm FIFO queue order and concurrency 1 (FR-026), and show a queue position message where available. Depends on T022, T082.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Quality gates and final checks

- [x] T086 [P] Run `ruff check`, `ruff format --check`, and `mypy server tests`, and fix all findings (constitution Principle I). Enforced on every PR by T093.
- [x] T087 [P] Add docstrings to public functions and classes in `server/`. Remove dead code and unused dependencies (constitution Principle I).
- [x] T088 Security pass: no secrets in logs, no path traversal through upload names, CSRF on every POST and DELETE, and no response reveals another user's data.
- [x] T089 Run the full `quickstart.md` validation with the `mock` provider and record the results in `specs/001-movie-video-generation/checklists/quickstart-run.md`.
- [x] T090 Spec gap (remediated): User Story 6 for FR-035 and FR-036 is now in spec.md. Re-run `/speckit-analyze` to confirm the gap is closed.
- [x] T091 [P] Write `tests/integration/test_latency.py`: the p95 latency of each non-generation endpoint (auth, job list, job detail, providers, health) is at most 300 ms at 5 concurrent users (constitution IV). Write it first and record the baseline in `tests/integration/latency_baseline.json`.
- [x] T092 Add the performance regression gate: fail the CI run when any endpoint's p95 is more than 10% above its recorded baseline (constitution IV). Depends on T091, T093.
- [x] T093 Create the CI pipeline `.github/workflows/ci.yml` that runs `ruff check`, `ruff format --check`, `mypy server tests`, unit tests, and contract tests (mock) on every pull request, plus the T051 accessibility scan for UI changes (constitution I, II, III, Development Workflow). Enable it as soon as Phase 1 completes. Depends on T004, T005.
- [x] T094 [P] Write `tests/integration/test_engine_swap.py`: changing `VIDEO_PROVIDER` in configuration, with no code change, switches the engine a job uses. The same submit-to-download flow passes with each configured provider (SC-008, FR-016). Write it first and confirm FAIL.
- [x] T095 [P] Write `tests/integration/test_delete_job.py`: `DELETE /api/jobs/{id}` by the owner returns `204` and removes the job's media (FR-038). A queued or running job returns `409 job_running`. Another user's job returns `404`. A request without the CSRF header returns `403 csrf_failed`. Write first and confirm FAIL.
- [x] T096 [P] Write `tests/integration/test_health_and_errors.py`: `GET /api/health` returns `{status, provider, queue}` without authentication. Every error response has the shape `{"error": {"code", "message"}}` (contracts/rest-api.md). Write first and confirm FAIL.
- [x] T097 [P] Write `tests/unit/test_model_validation.py`: `User.username` accepts 3–32 characters of letters, digits, and underscore, and is unique case-insensitively. The `User` password minimum is 12 characters (contracts/rest-api.md). `Job.progress` stays within 0–100. `Scene.position` is contiguous from 0. `SourceImage.alt_text` is at most 500 characters. Write first and confirm FAIL.
- [x] T098 [P] Write `tests/unit/test_progress.py`: progress writes keep `progress` within 0–100 and non-decreasing within one run, and each stage change writes a new `message` (FR-018). Write first and confirm FAIL.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T001 waits for the Python version decision.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **User Stories (Phases 3 to 8)**: All depend on Foundational. US1 and US2 are both P1 and can run in parallel. US3 and US4 depend on the job pipeline from US1 and US2.
- **Engine Choice (Phase 8)**: Depends on US1 (job creation, T029), US4's client (T057), and the provider base (T020).
- **Local Engine (Phase 9)**: Depends on T072 and T073 passing. T078 also depends on T071 (Phase 8). The other tasks in this phase do not depend on the user stories.
- **Retention and Operations (Phase 10)**: Depends on US1 (`run_job`).
- **Polish (Final Phase)**: Depends on all phases.

### User Story Dependencies

- **US1 (P1)**: Starts after Foundational. Independent.
- **US2 (P1)**: Starts after Foundational. Extends `POST /api/jobs` and `run_job` from US1, so merge after US1's T029 and T031.
- **US3 (P2)**: Depends on US2's mapping and I2V path (T038, T040).
- **US4 (P2)**: Depends on US1's job read path (T033). Its client work (T055 to T057) is the first UI.
- **US5 (P3)**: Depends on US1's `join` (T032) and on US4's client (T057).

### Within Each User Story

- Tests are written first and must FAIL before their implementation.
- Models before services, services before endpoints, endpoints before the client.

### Parallel Opportunities

- Setup: T005, T006, and T007 run in parallel.
- Foundational: T008, T009, T011, T014, T019 run in parallel.
- US1 tests (T023 to T027) run in parallel. In US1 implementation, only T030 is marked [P]. T028 and T032 follow their own tests and are not marked [P].
- Phases 3 and 4 can be written in parallel (tests only). US2 implementation (T039, T040) merges after US1's T029 and T031.

---

## Parallel Example: User Story 1

```bash
# Write the US1 tests together (they touch different files):
Task: "T023 tests/unit/test_split_paragraph.py"
Task: "T024 tests/unit/test_split_llm.py"
Task: "T025 tests/unit/test_job_validation.py"
Task: "T026 tests/integration/test_scenario_job.py"
Task: "T027 tests/integration/test_shot_retry.py"

# Then the independent implementation piece (T028 and T032 follow their tests, one at a time):
Task: "T030 server/worker/pipeline/progress.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001 to T007; T001 needs the Python version decision).
2. Complete Phase 2: Foundational (T008 to T022). This blocks everything.
3. Complete Phase 3: User Story 1 (T023 to T033).
4. **STOP and VALIDATE**: run the US1 independent test with the `mock` provider.
5. Demo the scenario-only flow through the API.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → validate → MVP.
3. US2 → validate photo-only mode.
4. US3 → validate combined mode.
5. US4 → browser client and live progress.
6. US5 → output options.
7. Phase 8 (User Story 6) → engine choice and cloud disclosure.
8. Phase 9 → local LTX-2.3, only after the license and VRAM gates (T072, T073) pass.
9. Phase 10 → retention and queue behavior, then Polish.

---

## Notes

- Test tasks come before implementation tasks in each phase, per constitution Principle II. Confirm FAIL before implementing.
- `[P]` marks tasks on different files with no unmet dependency.
- `[Story]` labels map each task to its user story in spec.md.
- Phases 9 and 10 carry no story label because they are not user stories. Phase 8 is User Story 6.
- Phase 9 is gated: T072 and T073 must pass first. Until then, all of Phases 1 to 7 run on the `mock` provider.
- Commit after each task or logical group.
- T095 to T098 are test-first tasks added by the second remediation. Their implementation tasks (T012, T013, T018, T030, and T054) depend on them, so run the tests first, even though the IDs sit in the Final Phase.

---

## Summary

- **Total tasks**: 98
- **Per story**: US1 11 (T023–T033), US2 7 (T034–T040), US3 7 (T041–T047), US4 11 (T048–T058), US5 5 (T059–T063), US6 8 (T064–T071)
- **Per non-story phase**: Setup 7, Foundational 15, Local engine 8, Retention 6, Polish 13 (T086–T098; T095 to T098 are test-first tasks added by remediation)
- **Parallel opportunities**: [P] on 46 tasks (a [P] marker is kept only where a task has no declared dependency)
- **Suggested MVP**: Phases 1 to 3 (T001 to T033), which deliver User Story 1
