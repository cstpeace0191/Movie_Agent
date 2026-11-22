# Implementation Plan: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Branch**: `002-transitions-captions-music` | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-transitions-captions-music/spec.md`

## Summary

Extend the feature 001 pipeline so a finished video can have scene transitions, captions written from
per-photo notes (reviewed by the user before generation), downloadable and optionally burned-in
subtitles, title and ending cards, and background music. Add a GPU-free "photo slideshow" engine.

Technical approach (details in [research.md](research.md)):

- A pure `timeline` module computes each scene's start and length from measured clip lengths and the
  chosen transitions. One `compose` module turns the timeline into a single FFmpeg filter graph that
  normalizes size and frame rate, applies `xfade`/`concat`, mixes audio, applies loudness
  normalization, and optionally burns in ASS subtitles. It replaces `join.py` (fixes the FR-013 gap).
- Captions are drafted by the Claude API (vision, structured output) in a **separate lightweight Celery
  queue**, so drafts are not stuck behind a GPU job. The job then waits in `awaiting_review`; the user
  edits and confirms, and only then is the generation task queued (FR-064).
- A `slideshow` provider implements `VideoProvider` with FFmpeg `zoompan`, declares
  `requires_photos=True`, and passes the shared contract suite with the capability-aware T2V case.
- New render options are stored as one JSON column on `Job`; new per-scene and per-photo fields are
  added as nullable columns through the existing lightweight column-migration helper in `db.py`.

## Technical Context

**Language/Version**: Python 3.11 (server, worker), TypeScript 5 + React 18 (client). Unchanged from 001.

**Primary Dependencies**: Existing: FastAPI, SQLAlchemy 2, Pydantic Settings, Celery 5, redis-py,
anthropic, httpx, FFmpeg (external binary). New: Pillow (downscale photos before sending them to the
text assistance service; read image size for slideshow crop). No new client libraries.
FFmpeg MUST be built with `libass` (subtitle burn-in) and include the `xfade`, `acrossfade`, `zoompan`,
`loudnorm` filters ([research R5](research.md)).

**Storage**: Same DB (SQLite dev / MySQL 9.3) and job directory `storage/jobs/<job_id>/`. New files per
job: `subtitles.srt`, `subtitles.ass`, `audio/bgm.<ext>`, `cards/title.mp4`, `cards/ending.mp4`.
Built-in music in `server/assets/music/` with `library.json`. Fonts in `server/assets/fonts/`.

**Testing**: pytest (unit / contract / integration), mock and slideshow providers for GPU-free
end-to-end runs, a fake text assistance client for unit tests, ffprobe-style probing (via FFmpeg) for
assertions on output size, fps, duration, and audio stream presence. `axe-core` scans for new UI.

**Target Platform**: Unchanged (Linux server with RTX 4090; Windows dev with `--pool=solo`).

**Project Type**: Web service (REST + SSE) with background workers and a React SPA.

**Performance Goals** (constitution IV budgets for the paths this feature changes):

- Non-generation endpoints, including the new review and caption endpoints: p95 ≤ 300 ms at 5 users.
- Job submission acknowledgment still ≤ 1 s (SC-004); caption drafting never runs in the request.
- Caption drafts ready ≤ 60 s after submission for ≤ 20 photos (SC-015), measured on the planning queue
  with no GPU job competing for it.
- Compose step (transitions + subtitles + music, no GPU): ≤ 10% of total job time (SC-012); target
  ≤ 60 s CPU for a 3-minute 832×480 video.
- Peak worker memory for compose ≤ 1.5 GB; VRAM use unchanged (compose and slideshow use no GPU).

**Constraints**:

- Shots stay 5–10 s; planned length (Σ scene lengths incl. cards, before transition overlap) ≤ 180 s.
- Transition length 0.1–2.0 s, clamped to half the shorter neighbouring scene.
- Audio upload: MP3/WAV/M4A, ≤ 30 MB, validated by magic bytes.
- Photos sent to the text assistance service only after recorded consent, downscaled to ≤ 1024 px.
- All new media follow the 2-day retention and delete rules.

**Scale/Scope**: ≤ 5 concurrent users; one GPU worker plus one planning worker. 3 new UI areas
(photo notes + render options in the create form, caption review screen, result extras). 11 new or
changed endpoints ([contracts/rest-api.md](contracts/rest-api.md)).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / rule | How this plan meets it | Status |
|------------------|------------------------|--------|
| I. Code Quality | New modules have one responsibility each (`timeline`, `compose`, `subtitles`, `audio`, `captions`, `providers/slideshow`). `timeline` is pure (no I/O). ruff + mypy cover all new code. `join.py` is removed once `compose` passes its tests, so no dead code remains. | PASS |
| II. Test-First | Tasks will start each step with failing tests: timeline math (property-style cases for clamping and totals), SRT/ASS cue times (SC-010), filter-graph construction, slideshow under the shared contract suite, review state transitions, consent gating. Text assistance is faked in unit tests; one opt-in integration test calls the real API. | PASS (enforced in tasks) |
| III. Accessibility | Notes field has its own label distinct from alt text; review screen is a keyboard-operable list with labelled caption inputs and a character/line counter announced via `aria-live`; burned captions use outline/box for ≥ 4.5:1; subtitle file always offered when captions exist. Captions are required for narrated video, and narration audio is not produced in this release. | PASS |
| IV. Performance | Budgets above. Drafting runs async on its own queue; compose has a measured budget; images are downscaled before upload; no model is loaded per request (the API client is created once per worker process). | PASS |
| Engine behind `VideoProvider`, switched by env var | `slideshow` is registered in `registry.py`. The API decides "needs photos" from provider metadata (`requires_photos`), not from the engine name, so no engine name appears outside `worker/providers/`. | PASS |
| Local open-weight default; license checks | No engine default changes. New third-party content (fonts, music) is limited to OFL fonts and tracks with stored license notices. MusicGen is not adopted. | PASS |
| Server owns generation | Captions, compose, and slideshow run in workers; the client only edits caption text and calls the API. | PASS |
| External data disclosure | Extends the FR-036 pattern to the text assistance service (FR-046): consent recorded per job; worker refuses to send without it. | PASS |

**Result**: All gates pass. One addition is recorded in Complexity Tracking (second worker queue).

## Project Structure

### Documentation (this feature)

```text
specs/002-transitions-captions-music/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   ├── rest-api.md      # Delta to specs/001 contracts/rest-api.md
│   └── video-provider.md# Delta: motion, requires_photos, slideshow contract cases
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
server/
├── app/
│   ├── api/jobs.py          # + new form fields, review/confirm/captions/subtitles/images routes
│   ├── api/music.py         # NEW: GET /api/music
│   ├── api/capabilities.py  # NEW: GET /api/capabilities (text_assist_available, music_library_available)
│   ├── models.py            # + Job.render_options etc., Scene/SourceImage fields, new statuses
│   ├── schemas.py           # + RenderOptions, SceneOut, ReviewCaptionsIn, MusicTrackOut
│   ├── db.py                # + column-migration entries for jobs/scenes/source_images
│   ├── storage.py           # + audio validation, subtitle/card/bgm paths
│   └── config.py            # + CAPTION_MODEL, PLANNING_QUEUE, MAX_AUDIO_SIZE_BYTES, FONTS_DIR, MUSIC_DIR
├── worker/
│   ├── celery_app.py        # + task routes: draft_captions -> "planning", run_job -> "generation"
│   ├── tasks.py             # + draft_captions_task; run_job uses timeline + compose
│   ├── pipeline/
│   │   ├── timeline.py      # NEW: pure timeline computation (FR-041, FR-042)
│   │   ├── compose.py       # NEW: timeline -> FFmpeg graph (normalize, xfade/concat, audio, burn-in)
│   │   ├── subtitles.py     # NEW: SRT + ASS writers (FR-047, FR-048)
│   │   ├── audio.py         # NEW: probe audio streams, bgm loop/fade args, loudnorm (FR-050, FR-051)
│   │   ├── cards.py         # NEW: title/ending card clips (FR-049)
│   │   ├── captions.py      # NEW: caption drafting via text assistance + verbatim fallback (FR-045)
│   │   ├── probe.py         # NEW: duration / size / fps / has-audio probing
│   │   └── join.py          # REMOVED after compose replaces it
│   └── providers/
│       ├── base.py          # + ShotRequest.motion, provider capability attributes
│       ├── slideshow.py     # NEW (FR-043)
│       └── registry.py      # + slideshow; provider metadata lookup
└── assets/
    ├── fonts/               # NEW: Noto Sans KR (OFL) + license
    └── music/               # NEW: library.json + tracks + licenses

client/src/
├── components/PhotoNotes.tsx     # NEW: per-photo note + alt text fields
├── components/RenderOptions.tsx  # NEW: transition, captions, style, cards, music, consent
├── components/CaptionReview.tsx  # NEW: awaiting_review screen
├── App.tsx / api.ts / types.ts / i18n.ts   # wiring, types, ko/en strings

compose.yaml, Dockerfile       # + second worker service "worker-planning" (-Q planning), FFmpeg with libass
README.md, 수행방법.md         # + two-worker run commands

tests/
├── unit/   test_timeline.py, test_subtitles.py, test_compose_graph.py, test_audio_args.py,
│           test_captions.py, test_cards.py, test_audio_upload_validation.py, test_render_options.py
├── contract/ test_provider_contract.py (+ slideshow, capability-aware T2V)
├── integration/conftest.py   # NEW: server + Playwright + axe fixtures (browser marker)
└── integration/ test_transitions_job.py, test_caption_review.py, test_subtitles_download.py,
                 test_bgm_job.py, test_slideshow_job.py, test_text_assist_consent.py
```

**Structure Decision**: Keep the existing `server/` + `client/` web layout from feature 001. New
behaviour goes into new single-purpose pipeline modules; existing modules change only at their
integration points (`tasks.py`, `api/jobs.py`, `models.py`). New client UI goes into new component
files so `App.tsx` (already 1,235 lines) does not grow further.

## Complexity Tracking

| Addition | Why Needed | Simpler Alternative Rejected Because |
|----------|------------|-------------------------------------|
| Second Celery queue (`planning`) with its own lightweight worker | Caption drafts must be ready within 60 s (SC-015) and must not wait behind a GPU job that can run 30 minutes on the single generation worker (FR-026). | Running drafting inside the request breaks SC-004 (1 s ack). Running it on the GPU queue makes users wait for unrelated jobs before they can review. |
| `ShotRequest.motion` field and provider capability attributes | The slideshow engine needs a motion per scene, and the API must reject photo-less jobs without naming the engine (FR-016). | Encoding motion in the prompt string is untestable; checking `provider == "slideshow"` in the API violates the engine-name rule. |

## Confirmed decisions (plan review 2026-11-21)

1. Caption model: `CAPTION_MODEL=claude-opus-5-5` by default; switching to `claude-haiku-5-5` is a
   configuration change after SC-011 is measured.
2. Two workers: `generation` (GPU, concurrency 1) and `planning` (no GPU).
3. Defaults: transition `none`, captions off, burn-in off (001 behaviour unchanged).
4. Music library ships empty and hidden until tracks and licenses are chosen (VERIFY 3); uploads work.
5. Title and ending cards: 3 s each, solid background, centred text.
6. Caption position "auto" resolves to bottom in this release; no face detection.

## Phase status

- Phase 0 research: complete ([research.md](research.md)), no open NEEDS CLARIFICATION.
- Phase 1 design: complete ([data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)).
- Post-design Constitution Check: re-evaluated after Phase 1, all gates still PASS (see end of research.md).
