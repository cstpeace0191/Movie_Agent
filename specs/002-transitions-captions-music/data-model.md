# Data Model: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Date**: 2026-11-21 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)
**Base**: [specs/001 data-model.md](../001-movie-video-generation/data-model.md). Only additions and
changes are listed. All new columns are nullable or have defaults, so existing rows stay valid
(research R13).

## Entity Relationships (changes in bold)

```text
User 1 ──< Job 1 ──< SourceImage (+ note)
                 1 ──< Scene (+ caption, kind, timeline fields) 1 ──? SourceImage
                 1 ──< Shot ──? Scene
                 1 ──? **render_options (JSON)**
                 1 ──? **subtitles.srt / subtitles.ass, audio/bgm.*, cards/*.mp4** (files)
MusicTrack (file catalog: server/assets/music/library.json) ──? Job.render_options.bgm_id
```

## Job (changes)

| Field | Type | Rules |
|-------|------|-------|
| status | enum | Adds `drafting`, `awaiting_review` (see transitions). Existing: `queued`, `running`, `succeeded`, `failed`, `expired`. |
| render_options | JSON | See RenderOptions. Default `{}` = all defaults (001 behaviour). |
| text_assist_consent_at | datetime? | Set when the user agreed (FR-046). Null = nothing may be sent. |
| review_confirmed_at | datetime? | Set on confirm (FR-064). |
| bgm_path | string? | Uploaded audio path inside the job directory. Null when library track or no music. |
| subtitles_srt_path | string? | Set after compose when the job has captions. |
| subtitles_ass_path | string? | Same. |
| final_duration_seconds | float? | Measured length of `final.mp4` (= Σd − Σt). |
| planned_seconds | float | Unchanged meaning; now includes card scenes (3 s each). |

### RenderOptions (JSON value object)

| Key | Type | Default | Rules |
|-----|------|---------|-------|
| transition | enum | `none` | `none, fade, fade_black, fade_white, dissolve, slide_left, slide_right, slide_up, slide_down, wipe_left, circle_open, zoom_in, auto` |
| transition_seconds | float | 0.5 | 0.1–2.0 |
| motion | enum | `auto` | `zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down, auto`; used by slideshow only |
| captions | bool | false | When false: no drafting, no review, no subtitles |
| caption_tone | enum | `informative` | `informative, emotional, humorous, travel_diary, advertisement` |
| burn_captions | bool | false | |
| caption_position | enum | `bottom` | `top, bottom, auto` (`auto` = bottom in this release) |
| caption_size | enum | `medium` | `small, medium, large` |
| caption_color | string | `#FFFFFF` | `#RRGGBB` |
| caption_box | bool | true | Opaque box behind text |
| title | string? | null | ≤ 80 chars, trimmed; empty = none |
| ending_text | string? | null | ≤ 120 chars |
| bgm_id | string? | null | Must exist in library.json; mutually exclusive with uploaded `bgm_path` |
| bgm_volume | float | 0.3 | 0.0–1.0 |

## Scene (changes)

| Field | Type | Rules |
|-------|------|-------|
| kind | enum | `scene` (default), `title`, `ending` |
| caption | text? | ≤ 2 lines × 42 chars after wrapping. Null when captions are off. |
| caption_source | enum? | `assisted` (rewritten by the service), `verbatim` (note/alt/scene text), `user` (edited in review) |
| narration | text? | Stored for Release 3; not voiced |
| transition | enum? | Null = use RenderOptions.transition. Transition **into** this scene; ignored for position 0. |
| motion | enum? | Null = RenderOptions.motion (auto resolves per position) |
| start_seconds | float? | Timeline result (research R1) |
| length_seconds | float? | Measured clip length used on the timeline |

Card scenes (`title`, `ending`) have no source image, no shot from a generation engine, and no caption.
`position` stays contiguous from 0 including cards.

## SourceImage (changes)

| Field | Type | Rules |
|-------|------|-------|
| note | string? | ≤ 500 chars (FR-044). Shown in job details. Separate from `alt_text`. |

## Shot (no column changes)

Cards produce Shot rows with `status=succeeded` and `attempts=0` so the shot list stays complete; their
`clip_path` points to `cards/*.mp4`.

## MusicTrack (catalog, not a table)

| Field | Type | Rules |
|-------|------|-------|
| id | string | Stable slug |
| title | string | Shown to the user |
| mood | string | e.g. calm, upbeat |
| duration_seconds | float | |
| file | string | Relative to `server/assets/music/`; never returned by the API |
| license_name, license_url, attribution | string | Shown on the result page (FR-050) |

## State transitions (Job)

```text
                 captions on                       confirm
 submit ──► drafting ──────────► awaiting_review ──────────► queued ──► running ──► succeeded
   │            │  (fallback still                │                       │
   │ captions   │   reaches review)               │ cancel / delete       └──► failed
   │ off        │ cancel / delete                 ▼
   └──────────► queued (001 path)            failed("Cancelled by user") / deleted
 any non-expired status ── retention deadline ──► expired
```

- Caption edits are accepted only in `awaiting_review` (FR-064); otherwise `409 not_in_review`.
- Confirm does not change `expires_at`.
- `drafting` and `awaiting_review` jobs are not counted in the generation queue (FR-026).

## Validation rules summary

- `image_notes[i]` ≤ 500 chars; `len(image_notes) ≤ len(images)`.
- Slideshow provider (any provider with `requires_photos=True`) with zero photos → `422 provider_needs_photos`.
- `planned_seconds = Σ scene durations + 3 s per card ≤ 180` → else `422 too_long` (message includes cards).
- Edited caption: after wrapping ≤ 2 lines of 42 chars, else `422 caption_too_long`.
- Audio upload: MP3/WAV/M4A by magic bytes, ≤ 30 MB → else `400 unsupported_audio_type` / `413 audio_too_large`.
- `bgm_id` and an uploaded file in the same request → `422 conflicting_music`.
