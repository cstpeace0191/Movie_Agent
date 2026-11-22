---

description: "Task list for feature 002: scene transitions, photo captions, subtitles, and background music"
---

# Tasks: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Input**: Design documents from `specs/002-transitions-captions-music/`

**Prerequisites**: [plan.md](plan.md) (required), [spec.md](spec.md) (required), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. Constitution Principle II (Test-First, NON-NEGOTIABLE) requires them. Every test task
is written first and MUST fail for the expected reason before its implementation task starts. Unit tests
use fakes for the text assistance service and never call the network.

**Organization**: Grouped by user story from spec.md: US1 transitions (P1), US2 captions and review (P1),
US3 subtitles/style/cards (P2), US4 background music (P2), US5 photo slideshow engine (P3).

**Remediation (2026-11-21)**: Fixes approved from `/speckit-analyze` for D1, U1, E1, I1, I2, C1, E2, and E3.
Added T078 to T087 (placed in their phases; IDs are out of order there).
Second analyze pass (2026-11-21): S1, I3, T1, and E5 fixed. Added T088 and T089 (browser test base and CI)
in Phase 1 and T090 (SC-009 end-to-end) in US5. plan.md and specify.txt updated. Amended T018, T029, T031, T032,
T045, and T064. spec.md FR-048 and FR-064 and contracts/rest-api.md (`GET /api/capabilities`) were updated.

**Confirmed decisions**: see plan.md "Confirmed decisions" (Opus caption model by default, two workers,
defaults off, empty music library, 3 s cards, auto position = bottom).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US5, user story phases only
- Paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, assets, and runtime prerequisites

- [x] T001 Add `pillow>=10.0` to `dependencies` in `pyproject.toml` and to `server/requirements.txt`; run `uv lock` to update `uv.lock`.
- [ ] T002 [P] (Deferred to US3: font files not downloaded during the MVP run; see server/assets/fonts/README.md) Add Noto Sans KR (Regular and Bold, OFL) to `server/assets/fonts/` with its `OFL.txt` license file.
- [x] T003 [P] Create `server/assets/music/library.json` containing an empty JSON array `[]` and `server/assets/music/LICENSES/README.md` explaining that each track needs `id, title, mood, duration_seconds, file, license_name, license_url, attribution` and its license text before release (research R10, VERIFY 3).
- [x] T004 [P] Add settings to `server/app/config.py`: `CAPTION_MODEL: str = "claude-opus-5-5"`, `CAPTION_CHUNK_SIZE: int = 20`, `CAPTION_IMAGE_MAX_PX: int = 1024`, `MAX_AUDIO_SIZE_BYTES: int = 30 * 1024 * 1024`, `FONTS_DIR: str = "server/assets/fonts"`, `MUSIC_DIR: str = "server/assets/music"`, `CARD_SECONDS: float = 3.0`; document each in `server/.env.example`.
- [ ] T005 (Dev machine verified 2026-11-21: bundled imageio-ffmpeg 9.0.2 has every filter and libass. Docker image not yet built and checked.) VERIFY 1 (research R5): on the dev machine and in the image built from `Dockerfile`, run `ffmpeg -hide_banner -filters` and confirm `subtitles`, `xfade`, `acrossfade`, `zoompan`, `loudnorm` exist. If `subtitles` is missing, change `Dockerfile` to install a distro FFmpeg built with libass and point `get_ffmpeg_cmd()` in `server/worker/pipeline/ffmpeg.py` at it. Record the result in research.md.
- [x] T006 VERIFY 2 (research R6): check the installed `anthropic` version in `uv.lock` supports `client.messages.parse(...)` structured output, `output_config={"effort": ...}`, and `client.beta.messages` with `fallbacks`; bump the pin in `pyproject.toml` if not. Record the exact call shape in research.md R6.
- [x] T007 [P] Add a `worker-planning` service to `compose.yaml` (same image and env as `worker`, command `celery -A server.worker.celery_app worker -Q planning --pool=solo --concurrency=1 -l info`, no GPU reservation) and change the existing `worker` command to `-Q generation`.
- [x] T088 Create the browser test base in `tests/integration/conftest.py`: a session-scoped fixture that builds the client once (`npm --prefix client run build`), starts the API on a free port with `ENV=test`, `VIDEO_PROVIDER=mock`, and Celery eager mode, and stops it after the session; a `logged_in_page` fixture that registers and verifies a test user through the API, sets the session cookie, and yields a Playwright Chromium `page`; and an `axe_scan(page) -> list[violation]` helper that injects `axe-core` (add `axe-core` as a devDependency in `client/package.json`, loaded from `client/node_modules/axe-core/axe.min.js`). Mark these tests with `@pytest.mark.browser` and register the marker in `pyproject.toml`. Required before T071 and T078–T082.
- [x] T089 [P] Add a browser-test step to `.github/workflows/ci.yml`: `npm ci --prefix client`, `pip install -e .[dev]`, `playwright install --with-deps chromium`, then `pytest -m browser tests/integration -v`. Keep the existing non-browser job unchanged so unit and contract tests still run without a browser.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, shared types, probing, provider metadata, and queue routing used by every story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests (write first, must fail)

- [x] T008 [P] Unit test `tests/unit/test_render_options.py`: parsing defaults yields `transition="none"`, `transition_seconds=0.5`, `motion="auto"`, `captions=False`, `caption_tone="informative"`, `burn_captions=False`, `caption_position="bottom"`, `caption_size="medium"`, `caption_color="#FFFFFF"`, `caption_box=True`, `title=None`, `ending_text=None`, `bgm_id=None`, `bgm_volume=0.3`; rejects `transition_seconds` outside 0.1–2.0, `bgm_volume` outside 0.0–1.0, `caption_color` not matching `#RRGGBB`, `title` over 80 chars, `ending_text` over 120 chars, and any enum value not in data-model.md RenderOptions.
- [x] T009 [P] Unit test `tests/unit/test_probe.py`: probing a generated 2 s 320×240 16 fps clip returns duration within 0.05 s, width, height, fps, and `has_audio=False`; a clip generated with a sine audio track returns `has_audio=True`.
- [x] T010 [P] Unit test `tests/unit/test_db_migration.py`: on a SQLite DB created with the 001 schema, running the column-migration helper adds every new column listed in data-model.md (jobs, scenes, source_images) without data loss, and running it twice is a no-op.

### Implementation

- [x] T011 Add columns in `server/app/models.py`: `Job.render_options` (JSON, default `{}`), `Job.text_assist_consent_at` (DateTime, nullable), `Job.review_confirmed_at` (DateTime, nullable), `Job.bgm_path` (String(500), nullable), `Job.subtitles_srt_path` (String(500), nullable), `Job.subtitles_ass_path` (String(500), nullable), `Job.final_duration_seconds` (Float, nullable); `Scene.kind` (String(16), default `"scene"`, values `scene|title|ending`), `Scene.caption` (Text, nullable), `Scene.caption_source` (String(16), nullable, values `assisted|verbatim|user`), `Scene.narration` (Text, nullable), `Scene.transition` (String(32), nullable), `Scene.motion` (String(16), nullable), `Scene.start_seconds` (Float, nullable), `Scene.length_seconds` (Float, nullable); `SourceImage.note` (String(500), nullable, "≤ 500 chars"). Update the `Job.status` comment to list `drafting, awaiting_review, queued, running, succeeded, failed, expired`. Make `Scene.description` allow empty text for card scenes.
- [x] T012 Extend the add-missing-columns helper in `server/app/db.py` to cover `jobs`, `scenes`, and `source_images` with the columns from T011 (SQLite and MySQL types), so T010 passes.
- [x] T013 [P] Create `server/app/render_options.py` with a Pydantic `RenderOptions` model and enums exactly as data-model.md RenderOptions, plus `parse_render_options(form_fields) -> RenderOptions` raising a typed error that maps to `422 invalid_render_option` with a message naming the field and allowed values (T008 passes).
- [x] T014 [P] Create `server/worker/pipeline/probe.py` with `probe_media(path) -> MediaInfo(duration_seconds, width, height, fps, has_audio)` using the FFmpeg binary from `server/worker/pipeline/ffmpeg.py` (T009 passes).
- [x] T015 Extend `server/worker/providers/base.py`: add `motion: str | None = None` as the last field of `ShotRequest`, and document `requires_photos: bool` and `sends_data_externally: bool` as required class attributes on `VideoProvider`. Set them on `LtxVideoProvider` (False/False), `GeminiVideoProvider` (False/True), and `MockVideoProvider` (False/False).
- [x] T016 Add `get_provider_class(name)` to `server/worker/providers/registry.py` and change `GET /api/providers` in `server/app/api/jobs.py` to read `requires_photos` and `sends_data_externally` from the provider class instead of hard-coded values, adding `requires_photos` to `ProviderOut` in `server/app/schemas.py` (contract delta). Replace the `chosen_provider == "gemini-omni-1.2-flash"` consent check with `provider_cls.sends_data_externally`.
- [x] T017 Add `task_routes` in `server/worker/celery_app.py`: `run_job` → `generation`; `draft_captions_task`, `expire_old_jobs_task`, `send_verification_email_task` → `planning`. Set `task_default_queue="generation"`.
- [x] T018 [P] Add `server/app/storage.py` path helpers: `get_subtitles_path(job_id, fmt)` (`subtitles.srt`/`subtitles.ass`), `get_bgm_path(job_id, ext)` (`audio/bgm.<ext>`), `get_card_path(job_id, kind)` (`cards/<kind>.mp4`); all inside `get_job_dir(job_id)` so `delete_job_media` removes them.
- [x] T019 Extend `JobOut` in `server/app/schemas.py` with `render_options: dict`, `scenes: list[SceneOut] | None`, `text_assist_consented: bool`, `subtitles: SubtitleLinks | None`, `music: MusicCredit | None`, `final_duration_seconds: float | None`; add `SceneOut` with the fields in contracts/rest-api.md `GET /api/jobs/{id}`. Populate them in `GET /api/jobs/{id}` in `server/app/api/jobs.py`.

**Checkpoint**: Foundation ready. Feature 001 test suite still passes (`pytest tests -v`).

---

## Phase 3: User Story 1 - Smooth Transitions Between Scenes (Priority: P1) 🎯 MVP

**Goal**: Scenes are placed on one timeline, normalized, and joined with the chosen transition (FR-041, FR-042).

**Independent Test**: Photos-only job, 4 photos, mock provider, transition `fade`: visible fades, one frame size, length = Σd − 3 × t.

### Tests for User Story 1 (write first, must fail)

- [x] T020 [P] [US1] Unit test `tests/unit/test_timeline.py`: (a) 3 scenes of 5 s, transition `none` → starts 0, 5, 10, total 15; (b) `fade` 1.0 s → starts 0, 4, 8, total 13; (c) transition 2.0 s with a 3 s neighbour is clamped to 1.5 s ("MUST NOT be longer than half of either scene"); (d) one scene → no transition, total = its length; (e) `auto` over 6 scene changes yields no two consecutive equal styles; (f) per-scene override beats the job default; (g) measured length shorter than requested is used.
- [x] T021 [P] [US1] Unit test `tests/unit/test_compose_graph.py`: the built `filter_complex` normalizes every input with `scale=W:H:force_original_aspect_ratio=decrease,pad=W:H` and `fps=F`, uses `xfade=transition=<mapped>:duration=t:offset=s` only where `t > 0` and `concat` elsewhere, maps spec names to xfade names exactly as research R3, and emits no audio map when no input has audio.
- [x] T022 [P] [US1] Integration test `tests/integration/test_transitions_job.py`: with the mock provider, (a) default options produce a video whose scene count, order, and length equal the 001 result (15 s ± 0.1 for 3 photos) and no audio stream; (b) `transition=fade`, `transition_seconds=1.0` gives 13 s ± 0.1 and `scenes[].start_seconds == [0, 4, 8]`; (c) clips of 832×480 and 640×480 inputs produce a single 832×480 output at the job fps; (d) invalid `transition` returns `422 invalid_render_option`.
- [x] T078 [P] [US1] Playwright test `tests/integration/test_client_render_options.py`: using only the keyboard (Tab, arrow keys, Enter), choose transition "fade" and length 1.0 in the job form and submit; the captured `POST /api/jobs` request contains `transition=fade` and `transition_seconds=1.0`; a length of 2.5 shows a text error and is not submitted.

### Implementation for User Story 1

- [x] T023 [US1] Create `server/worker/pipeline/timeline.py`: `TimelineScene`, `Timeline`, and pure `build_timeline(lengths, transitions, default_transition, transition_seconds) -> Timeline` implementing research R1 rules and the `auto` cycle `fade, slide_left, dissolve, wipe_left, circle_open, slide_up` (T020 passes).
- [x] T024 [US1] Create `server/worker/pipeline/compose.py`: `build_compose_command(timeline, clips: list[MediaInfo + path], width, height, fps, output_path, extras) -> list[str]` and `compose(...)` that runs it to a temp file and atomically replaces `final.mp4`. Video per research R2 and R3. Scene audio per research R4 first paragraph: if any clip has audio, add `anullsrc` for clips without audio and join with `acrossfade=d=t` where `t > 0` else `concat`. Encode `libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -movflags +faststart` (T021 passes).
- [x] T025 [US1] Update `run_job_sync` in `server/worker/tasks.py`: after all shots succeed, probe each clip (`probe.py`), build the timeline from `Job.render_options` and `Scene.transition`, write `Scene.start_seconds`/`Scene.length_seconds`, call `compose`, store `Job.final_duration_seconds`. Progress messages: "Joining scenes" at 90.
- [x] T026 [US1] Parse `transition` and `transition_seconds` form fields in `POST /api/jobs` in `server/app/api/jobs.py` through `parse_render_options` and save into `Job.render_options`.
- [x] T027 [US1] Delete `server/worker/pipeline/join.py` and its imports; move any 001 join tests in `tests/unit/` to target `compose.py` so they still pass (T022 passes).
- [x] T028 [P] [US1] Create `client/src/components/RenderOptions.tsx` with a labelled transition `<select>` (all 13 values, default "none") and a numeric length input (0.1–2.0, step 0.1, default 0.5) with visible text constraints; wire into the job form in `client/src/App.tsx`, add fields to `client/src/api.ts` and `client/src/types.ts`, and add ko/en strings to `client/src/i18n.ts`.

**Checkpoint**: US1 works on its own; FR-013 gap from 001 is closed.

---

## Phase 4: User Story 2 - Captions Written from Notes on Each Photo (Priority: P1)

**Goal**: Per-photo notes → caption drafts → user review and confirm → video with plain subtitle file (FR-044, FR-045, FR-046, FR-064, SRT part of FR-047).

**Independent Test**: 3 photos with notes, captions on, consent on: job reaches `awaiting_review` without shots; edit one caption; confirm; SRT shows captions, edited one verbatim.

**Depends on**: US1 timeline (cue times).

### Tests for User Story 2 (write first, must fail)

- [ ] T029 [P] [US2] Unit test `tests/unit/test_captions.py` with a fake text assistance client: (a) chunks of at most `CAPTION_CHUNK_SIZE` scenes per request; (b) images are downscaled to ≤ 1024 px long edge before sending; (c) the basis order is note, then alt text, then the photo; (d) API error, `stop_reason == "refusal"`, invalid schema, missing key, or `text_assist_consent_at is None` → verbatim caption from note/alt/scene text with `caption_source="verbatim"` and no request sent when consent is missing; (e) every caption is wrapped to at most 2 lines of 42 chars, verbatim text cut with an ellipsis; (f) photos not mapped to any scene (more photos than scenes, FR-010) produce no caption and are not sent to the service, even when they have notes.
- [ ] T030 [P] [US2] Unit test `tests/unit/test_subtitles_srt.py`: SRT cue i spans `[s_i + t_i/2, s_{i+1} + t_{i+1}/2)` and the last cue ends at the total length; card scenes produce no cue; output is UTF-8 without BOM; Korean and English text round-trip unchanged.
- [ ] T031 [P] [US2] Integration test `tests/integration/test_caption_review.py`: `captions=true` → `201` with `status="drafting"`; job reaches `awaiting_review` and no shot file exists; `PATCH /api/jobs/{id}/captions` updates caption 1 with `caption_source="user"`; a caption longer than 2 × 42 chars → `422 caption_too_long`; unknown position → `422 unknown_position`; `POST /confirm` → `queued`, second confirm → `409 not_in_review`; PATCH after confirm → `409 not_in_review`; cancel and delete succeed in `drafting` and `awaiting_review`; a job cancelled while drafting stays cancelled after the drafting task finishes; `captions=false` → straight to `queued`; a TEXT_IMAGE job with 4 photos and 2 scenes has captions only for the 2 mapped scenes, and `unused_image_count == 2` (spec edge case on unused photos' notes).
- [ ] T032 [P] [US2] Integration test `tests/integration/test_text_assist_consent.py`: with consent off, the fake client receives zero calls and captions equal the wrapped notes; with consent on, `Job.text_assist_consent_at` is set and the fake client receives the notes and downscaled images; `split_with_llm(text, consent=False, client=fake)` returns the paragraph split and makes zero calls (FR-046 covers scene splitting too).
- [ ] T084 [P] [US2] Integration test `tests/integration/test_capabilities.py`: `GET /api/capabilities` requires login; returns `text_assist_available=false` with no Anthropic credential configured and `true` with a configured fake credential; `music_library_available=false` with the shipped empty library and `true` with a one-track fixture; the response contains no model name, key, or path.
- [ ] T079 [P] [US2] Playwright test `tests/integration/test_client_caption_review.py`: (a) the photo preview shows separately labelled "Alt text" and "Note for caption" fields, and the submitted request carries `image_alt_texts` and `image_notes` as separate JSON arrays; (b) with `text_assist_available=true`, turning captions on shows the disclosure text and an unchecked consent checkbox, and leaving it unchecked shows the "notes will be used as written" text; with `false`, no disclosure is shown; (c) on an `awaiting_review` job, using only the keyboard, edit caption 2, Save, then Confirm; the PATCH and confirm requests are sent once each, the character counter is announced via `aria-live`, and a `422 caption_too_long` response is shown as text.
- [ ] T033 [P] [US2] Integration test `tests/integration/test_subtitles_download.py`: after success, `GET /api/jobs/{id}/subtitles?format=srt` returns attachment `movie-{id}.srt` whose cue starts match `scenes[].start_seconds` adjusted by half the transition within 0.1 s (SC-010); before success `409 not_ready`; captions off `404 no_subtitles`; other user `404 not_found`; bad format `422 invalid_format`.
- [ ] T034 [P] [US2] Integration test addition in `tests/integration/test_sse_events.py`: a job reaching `awaiting_review` emits `progress` events with `drafting` then `event: review` and the stream closes.

### Implementation for User Story 2

- [ ] T035 [US2] Parse `image_notes` (JSON array, "each ≤ 500 chars", length ≤ number of images), `captions`, `caption_tone`, and `text_assist_consent` in `POST /api/jobs` in `server/app/api/jobs.py`; store `SourceImage.note`, `Job.render_options`, and `Job.text_assist_consent_at` (only when consent is true); set initial status `drafting` and send `draft_captions_task` when captions are on, else keep the 001 path.
- [ ] T086 [US2] Add a required keyword argument `consent: bool` to `split_with_llm` in `server/worker/pipeline/split.py`; when `consent` is false it returns `split_by_paragraphs(...)` without creating or calling a client. Update `tests/unit/test_split_llm.py` callers (T032 split case passes).
- [ ] T083 [US2] Add `GET /api/capabilities` (authenticated) in a new `server/app/api/capabilities.py` per contracts/rest-api.md, register it in `server/app/main.py`, and add `getCapabilities()` to `client/src/api.ts` with its type in `client/src/types.ts` (T084 passes).
- [ ] T036 [US2] Create `server/worker/pipeline/captions.py`: `draft_captions(job, scenes, images) -> list[CaptionDraft]` per research R6 using the call shape recorded in T006, a module-level client created once per process, `CAPTION_MODEL`, effort `low`, server-side refusal fallbacks (`fallbacks="default"`), Pydantic schema `{captions: [{position, caption, narration}]}`, Pillow downscale, and the verbatim fallback with 2 × 42 wrapping (T029 passes).
- [ ] T037 [US2] Add `draft_captions_task(job_id)` in `server/worker/tasks.py`: load job and scenes, call `draft_captions`, write `Scene.caption`, `Scene.caption_source`, `Scene.narration`, then conditionally update `status` from `drafting` to `awaiting_review` (`UPDATE ... WHERE status='drafting'`); if the job is no longer `drafting`, discard drafts.
- [ ] T038 [US2] Add `PATCH /api/jobs/{id}/captions` and `POST /api/jobs/{id}/confirm` in `server/app/api/jobs.py` per contracts/rest-api.md (CSRF, ownership `404`, `409 not_in_review`, `422 caption_too_long`, `422 unknown_position`); confirm performs a conditional update `awaiting_review → queued`, sets `review_confirmed_at`, leaves `expires_at` unchanged, and enqueues `run_job` once.
- [ ] T039 [US2] Extend `POST /api/jobs/{id}/cancel` and `DELETE /api/jobs/{id}` in `server/app/api/jobs.py` to accept `drafting` and `awaiting_review`; `DELETE` keeps `409 job_running` for `queued`/`running`.
- [ ] T040 [US2] Add `GET /api/jobs/{id}/images/{image_id}` in `server/app/api/jobs.py` returning the stored photo with its media type; `404` for other users or expired jobs.
- [ ] T041 [US2] Update the SSE generator in `server/app/api/jobs.py` to emit `drafting`/`awaiting_review` progress, then `event: review` and close when status is `awaiting_review` (T034 passes).
- [ ] T042 [US2] Create `server/worker/pipeline/subtitles.py` with `write_srt(timeline, scenes, path)` per research R5 cue rules (T030 passes); call it from `run_job_sync` when captions are on and store `Job.subtitles_srt_path`.
- [ ] T043 [US2] Add `GET /api/jobs/{id}/subtitles?format=srt|ass` in `server/app/api/jobs.py` per contracts/rest-api.md (ASS returns `404 no_subtitles` until US3 writes it) (T033 passes).
- [ ] T044 [P] [US2] Create `client/src/components/PhotoNotes.tsx`: for each selected photo, a preview with two separately labelled fields, "Alt text" and "Note for caption" (each max 500, live character count announced via `aria-live="polite"`); replace the alt-text inputs in `client/src/App.tsx`; send `image_notes` in `client/src/api.ts`.
- [ ] T045 [P] [US2] Add to `client/src/components/RenderOptions.tsx`: captions on/off checkbox (default off), tone select (5 values), and, when captions are on and `GET /api/capabilities` returns `text_assist_available=true`, a text disclosure listing what is sent (scenario, notes, alt text, photos) with a required consent checkbox; unchecked consent shows text that notes will be used as written.
- [ ] T046 [US2] Create `client/src/components/CaptionReview.tsx`: shown for `awaiting_review` jobs; ordered list of scenes with photo (from `/images/{id}`, alt text as `alt`) or scene excerpt, the note, and a labelled caption `<textarea>` with a "2 lines × 42 characters" counter; "Save" (PATCH) and "Confirm and generate" (POST confirm) buttons reachable by Tab; text errors only. Route to it from the job detail in `client/src/App.tsx`; reconnect SSE after confirm. Add ko/en strings to `client/src/i18n.ts`.

**Checkpoint**: US1 + US2 deliver the main user request (photo story with reviewed captions).

---

## Phase 5: User Story 3 - Subtitle File, Readable On-Screen Text, and Title Cards (Priority: P2)

**Goal**: ASS subtitles, optional burn-in with style, and title/ending cards (FR-047, FR-048, FR-049).

**Independent Test**: Captions + title + ending + burn-in bottom: cards at start/end, captions drawn at bottom, SRT and ASS downloadable, cues aligned.

### Tests for User Story 3 (write first, must fail)

- [x] T047 [P] [US3] Unit test `tests/unit/test_subtitles.py`: ASS uses font "NanumGothic", 9 positions (`top_left`, `top_center`, `top_right`, `middle_left`, `middle_center`, `middle_right`, `bottom_left`, `bottom_center`, `bottom_right`, `none`), outline 3 and shadow 1, `BorderStyle=3` (60% opaque background box), cue times identical to SRT.
- [ ] T048 [P] [US3] Unit test `tests/unit/test_cards.py`: `render_card(text, kind, width, height, fps)` produces a `CARD_SECONDS` (3.0 s) clip at the job size and fps with no audio; empty or whitespace text produces no card.
- [x] T049 [P] [US3] Unit test addition in `tests/unit/test_compose_graph.py`: with `burn_captions=true`, the last video filter is `subtitles=<ass>:fontsdir=<FONTS_DIR>`; without it, no subtitles filter.
- [ ] T050 [P] [US3] Integration test `tests/integration/test_cards_and_burnin.py`: title + ending add 6 s to planned length; a job that exceeds 180 s only because of cards → `422 too_long` naming card seconds; finished video starts and ends with cards; ASS download works; `title` > 80 chars → `422 invalid_render_option`.

### Implementation for User Story 3

- [ ] T080 [P] [US3] Playwright test `tests/integration/test_client_subtitle_options.py`: keyboard-only, set burn-in on, position "Automatic (bottom)", size "large", colour, box off, title, and ending; the submitted request carries each value; a 81-character title shows a text error; on a succeeded job with captions, the result view shows SRT and ASS download links with accessible names.
- [ ] T087 [P] [US3] Unit test addition in `tests/unit/test_subtitles_ass.py`: burn a test caption with the default style (white text, outline 3, box on) onto an all-white and an all-black 832×480 frame; the measured contrast ratio between text pixels and their immediate surround is ≥ 4.5:1 in both frames (FR-048).
- [x] T051 [US3] Add `write_ass(timeline, scenes, style, path)` to `server/worker/pipeline/subtitles.py` supporting all 9 screen positions and call it from `run_job_sync`, storing `Job.subtitles_ass_path`.
- [ ] T052 [US3] Create `server/worker/pipeline/cards.py` with `render_card` using FFmpeg `color` source + `drawtext` (font from `FONTS_DIR`, centred, wrapped) (T048 passes).
- [x] T053 [US3] In `POST /api/jobs` in `server/app/api/jobs.py`, parse `burn_captions`, 9-position `caption_position`, map uploaded photo descriptions (`alt_text`) to `Scene.caption`; create subtitle download endpoints `GET /api/jobs/{id}/subtitles?format=srt|ass`.
- [x] T054 [US3] In `run_job_sync` in `server/worker/tasks.py`, write ASS and SRT subtitle files when captions exist, and in `compose.py`, append the `subtitles` filter with font path escaping when `burn_captions` is true.
- [x] T055 [P] [US3] Add to `client/src/components/RenderOptions.tsx`: 9 caption position selector (Top-Left, Top-Center, Top-Right, Middle-Left, Middle-Center, Middle-Right, Bottom-Left, Bottom-Center, Bottom-Right, None) with bilingual ko/en labels; pass caption options on job submission.

**Checkpoint**: US3 works on top of US2.

---

## Phase 6: User Story 4 - Background Music (Priority: P2)

**Goal**: Library or uploaded music, looped, faded, mixed, and loudness-normalized (FR-050, FR-051).

**Independent Test**: Video longer than the track: music repeats, fades in/out, ~−14 LUFS; licence shown for library tracks.

### Tests for User Story 4 (write first, must fail)

- [ ] T056 [P] [US4] Unit test `tests/unit/test_audio_upload_validation.py`: MP3 (`ID3` and frame-sync header), WAV (`RIFF....WAVE`), and M4A (`ftyp`) are accepted; other bytes → `unsupported_audio_type`; > 30 MB → `audio_too_large`.
- [ ] T057 [P] [US4] Unit test `tests/unit/test_audio_args.py`: for total length T, music input uses `-stream_loop -1`, `atrim=duration=T`, `afade=t=in:d=1`, `afade=t=out:st=T-2:d=2`, `volume=v`, `amix` with `normalize=0` when scene audio exists, and `loudnorm=I=-14:TP=-1.5:LRA=11`; no audio inputs and no music → no audio output.
- [ ] T058 [P] [US4] Integration test `tests/integration/test_bgm_job.py`: uploaded 10 s MP3 on a 20 s video → output audio length equals video length ± 0.1 s; integrated loudness within −14 ± 1 LUFS; `bgm` and `bgm_id` together → `422 conflicting_music`; unknown `bgm_id` → `422 invalid_render_option`; a 31 MB file → `413 audio_too_large`; deleting the job removes `audio/bgm.*`.
- [ ] T059 [P] [US4] Integration test `tests/integration/test_music_library.py`: `GET /api/music` returns `[]` with the shipped empty library and, with a test library fixture, returns entries without the `file` field; job detail `music` shows title and licence for a library track.
- [ ] T081 [P] [US4] Playwright test `tests/integration/test_client_music.py`: with `music_library_available=false` the library choice is not shown; the file input accepts `.mp3,.wav,.m4a` and states the 30 MB limit in text; the volume slider is keyboard-operable and its value is shown as text (default "30%"); the submitted request carries `bgm` and `bgm_volume`; on a succeeded job with a library track, the result view shows title and licence.

### Implementation for User Story 4

- [ ] T060 [US4] Add `validate_audio_upload(data, filename) -> (media_type, ext)` to `server/app/storage.py` (T056 passes).
- [ ] T061 [US4] Create `server/app/music_library.py` loading `MUSIC_DIR/library.json` once, and `server/app/api/music.py` with `GET /api/music`; register the router in `server/app/main.py` (T059 passes).
- [ ] T062 [US4] In `POST /api/jobs` in `server/app/api/jobs.py`, accept `bgm` (file), `bgm_id`, `bgm_volume`; save upload to `get_bgm_path`, set `Job.bgm_path`; validate per data-model.md rules.
- [ ] T063 [US4] Create `server/worker/pipeline/audio.py` with `music_filter_args(source, total_seconds, volume, has_scene_audio)` and `loudnorm_args()` (T057 passes); integrate into `compose.py` so music and loudness apply after the video timeline, and no audio stream is written when there is neither scene audio nor music (T058 passes).
- [ ] T064 [P] [US4] Add to `client/src/components/RenderOptions.tsx`: music choice (none / upload / library list hidden when `GET /api/capabilities` returns `music_library_available=false`), file input accepting `.mp3,.wav,.m4a` with the 30 MB limit stated in text, volume slider 0–100% (default 30%) with a numeric label; show title and licence on the result view in `client/src/App.tsx`; add ko/en strings.

**Checkpoint**: US4 works with US1 alone (no captions needed).

---

## Phase 7: User Story 5 - Photo Videos Without a Generation Engine (Priority: P3)

**Goal**: GPU-free `slideshow` provider with motion (FR-043).

**Independent Test**: No generation engine available; 5 photos, slideshow: job succeeds with zoom/pan scenes.

### Tests for User Story 5 (write first, must fail)

- [ ] T065 [P] [US5] Update `tests/contract/test_provider_contract.py`: parametrize over all registered providers that can run in CI (mock, slideshow); make the T2V test capability-aware (`requires_photos=True` → permanent `ProviderError`, no file); add tests "motion is honoured", "unknown motion", and "attributes present" per contracts/video-provider.md.
- [ ] T066 [P] [US5] Integration test `tests/integration/test_slideshow_job.py`: 5 photos with `provider=slideshow`, `motion=zoom_in` succeeds and every scene's first and last frames differ; `motion=auto` gives different motions for consecutive scenes; scenario-only job with slideshow → `422 provider_needs_photos`; TEXT_IMAGE job with more scenes than photos follows FR-009 (uses last photo or previous frame).
- [ ] T090 [P] [US5] Integration test `tests/integration/test_full_slideshow_story.py` (SC-009): with no generation engine reachable, a job of 10 photos with notes, `provider=slideshow`, `transition=fade`, `captions=true`, consent on (fake text assistance client), and an uploaded 10 s test MP3 goes `drafting → awaiting_review`; after confirm it succeeds; the video has 10 scenes, fades, an audio stream as long as the video, and an SRT with 10 cues.
- [ ] T082 [P] [US5] Playwright test `tests/integration/test_client_slideshow.py`: the motion select appears only when the chosen provider has `requires_photos=true`; choosing such a provider with no photos shows a text notice and the submit is blocked; the motion choice is keyboard-operable and sent as `motion`.

### Implementation for User Story 5

- [ ] T067 [US5] Create `server/worker/providers/slideshow.py` (`name="slideshow"`, `requires_photos=True`, `sends_data_externally=False`) implementing research R9 zoompan expressions, 5–10 s duration rule, no audio, permanent errors for missing image and unknown motion; register it in `server/worker/providers/registry.py` and list it in `GET /api/providers` with `max_clip_seconds: 10` in all environments (T065 passes).
- [ ] T068 [US5] In `server/worker/tasks.py`, resolve `motion` per scene (`Scene.motion` or `render_options.motion`; `auto` cycles `zoom_in, pan_left, zoom_out, pan_right, pan_up, pan_down`) and pass it in `ShotRequest.motion`.
- [ ] T069 [US5] In `POST /api/jobs` in `server/app/api/jobs.py`, parse `motion` and reject jobs with zero photos when the chosen provider class has `requires_photos=True` with `422 provider_needs_photos` ("This engine needs photos.") (T066 passes).
- [ ] T070 [P] [US5] In `client/src/components/RenderOptions.tsx`, show the motion select only when the chosen provider has `requires_photos=true`, and show a text notice when such a provider is chosen with no photos; add ko/en strings.

**Checkpoint**: All five stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T071 [P] Add an accessibility test in `tests/integration/test_a11y.py` that runs axe-core on the create form with all new controls and on the caption review screen; zero serious or critical violations (constitution III, SC-014).
- [ ] T072 [P] Add `tests/integration/test_retention.py` cases (or extend the existing retention test) asserting subtitles, cards, and uploaded audio are deleted at expiry and that `drafting`/`awaiting_review` jobs expire like others.
- [ ] T085 Build the SC-011 caption evaluation in `tests/eval/caption_eval.py` with 50 fixed inputs in `tests/eval/fixtures/captions/` (photo, note, alt text, tone, and a list of the facts each input allows). For each generated caption, record (a) any stated fact not in the allowed list and (b) a tone match yes/no from two reviewers (a rubric file, `tests/eval/caption_rubric.md`). Pass = zero unsupported facts and ≥ 90% tone match. The script calls the real service, so it runs only by hand with approval of the cost, never in CI. Run it for `claude-opus-5-5` and `claude-haiku-5-5` and record both results and costs in research.md R6, so the `CAPTION_MODEL` default can be reviewed.
- [ ] T073 Measure SC-012 and SC-015 per quickstart steps 5 and 10; record compose time, drafting time for 20 photos, and peak compose memory in `tests/integration/latency_baseline.json` and in plan.md Performance Goals; any budget overrun > 10% blocks merge until justified.
- [ ] T074 [P] Update `README.md` and `수행방법.md` with the two-worker commands, FFmpeg/libass requirement, `CAPTION_MODEL`, fonts, and music library notes.
- [ ] T075 [P] Update `specify.txt`: mark FR-041 to FR-051 and FR-064 as implemented, and close 16장 #2 (FR-013) once T027 merges.
- [ ] T076 Run `ruff check .`, `ruff format --check .`, `mypy server tests`, and the full `pytest tests -v`; fix all failures.
- [ ] T077 Run every manual scenario in `specs/002-transitions-captions-music/quickstart.md` and record pass/fail in `specs/002-transitions-captions-music/checklists/quickstart-run.md`.

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: none. T005 and T006 are verifications that may change T024/T036 details. T088 must finish before any `@pytest.mark.browser` test (T071, T078–T082) is written.
- **Foundational (Phase 2)**: after Setup; blocks all stories.
- **US1 (Phase 3)**: after Phase 2. Provides `timeline.py` and `compose.py` used by US2–US4.
- **US2 (Phase 4)**: after US1 (needs timeline for SRT cues).
- **US3 (Phase 5)**: after US2 (extends subtitles and caption options).
- **US4 (Phase 6)**: after US1 only; can run in parallel with US2/US3 (touches `audio.py`, `music.py`, and separate parts of `compose.py` — coordinate edits to `compose.py` and `jobs.py`).
- **US5 (Phase 7)**: after Phase 2 only; can run in parallel with US1–US4 (new provider file; small edits to `tasks.py`/`jobs.py`).
- **Polish (Phase 8)**: after the stories in scope.

### Story completion order

```text
Setup → Foundational → US1 ─┬─► US2 ─► US3
                            └─► US4
         Foundational ──────────► US5
```

### Within each story

Tests first (must fail) → models/pipeline modules → worker integration → API → client.

## Parallel Examples

- **Phase 2**: T008, T009, T010 together; then T013, T014, T018 together.
- **US1**: T020, T021, T022, T078 together; T028 (client) alongside T023–T027.
- **US2**: T029–T034, T084, T079 together; T044 and T045 (client) alongside T086, T083, T036–T043.
- **US3**: T047–T050, T080, T087 together; T055 alongside T051–T054.
- **US4**: T056–T059, T081 together; T064 alongside T060–T063.
- **US5**: T065, T066, T082, T090 together (T090 also needs US2 and US4 done); T070 alongside T067–T069.
- **Cross-story**: US5 can be built by a second developer during US1; US4 during US2.

## Implementation Strategy

### MVP

Phases 1–3 (US1): normalized joins and transitions. Ships the FR-013 fix and visible polish with no
external service and no UI flow change.

### Incremental delivery

1. MVP (US1) → demo with mock provider.
2. + US2 → the requested "photo + note → captioned video" with review.
3. + US5 → GPU-free path for demos and CI (can land earlier, it is independent).
4. + US3 → burn-in, styling, cards.
5. + US4 → music (library stays hidden until VERIFY 3).

Each increment keeps the 001 suite green and passes its own independent test before the next starts.
