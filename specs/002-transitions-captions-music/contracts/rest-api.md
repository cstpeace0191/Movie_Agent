# Contract Delta: REST and SSE API (feature 002)

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Data**: [data-model.md](../data-model.md)
**Base**: [specs/001 contracts/rest-api.md](../../001-movie-video-generation/contracts/rest-api.md).
All 001 conventions apply (session cookie, `X-CSRF-Token` on POST/PATCH/DELETE, error shape,
ownership → `404 not_found`). Only new or changed parts are listed.

## GET /api/providers (changed)

Each item adds `requires_photos: bool`. New item:

```json
{"id": "slideshow", "label": "Photo slideshow (no generation engine)", "location": "local",
 "enabled": true, "is_default": false, "sends_data_externally": false,
 "max_clip_seconds": 10, "requires_photos": true, "disabled_reason": null}
```

## POST /api/jobs (new parts)

| Part | Type | Default | Rule |
|------|------|---------|------|
| image_notes | string (JSON array) | none | Entry i is the note for `images[i]`; each ≤ 500 chars (FR-044) |
| transition | string | `none` | See RenderOptions enum (FR-042) |
| transition_seconds | float | 0.5 | 0.1–2.0 |
| motion | string | `auto` | Slideshow only (FR-043) |
| captions | bool | false | FR-045 |
| caption_tone | string | `informative` | |
| burn_captions | bool | false | FR-047 |
| caption_position / caption_size / caption_color / caption_box | string / string / string / bool | bottom / medium / #FFFFFF / true | FR-048 |
| title / ending_text | string | none | FR-049; cards add 3 s each to planned length |
| bgm | file | none | MP3/WAV/M4A ≤ 30 MB (FR-050) |
| bgm_id | string | none | From `GET /api/music` |
| bgm_volume | float | 0.3 | 0–1 |
| text_assist_consent | bool | false | FR-046; without it nothing is sent to the text assistance service |

Responses:

- `201`: as in 001, plus `"status": "drafting"` when `captions=true`, otherwise `"queued"`.
- New errors: `422 provider_needs_photos`, `422 invalid_render_option` (message names the field and the
  allowed values), `422 conflicting_music`, `400 unsupported_audio_type`, `413 audio_too_large`.
  `422 too_long` message now states card seconds separately.

## GET /api/jobs/{id} (changed)

Adds:

```json
{"render_options": {"transition": "fade", "transition_seconds": 0.5, "captions": true, "...": "..."},
 "scenes": [{"position": 0, "kind": "scene", "source_image_id": "uuid", "image_url": "/api/jobs/{id}/images/{image_id}",
             "note": "Grandma's 80th birthday", "alt_text": "…", "excerpt": "…",
             "caption": "…", "caption_source": "assisted", "start_seconds": 0.0, "length_seconds": 5.0}],
 "text_assist_consented": true,
 "subtitles": {"srt_url": "/api/jobs/{id}/subtitles?format=srt", "ass_url": "/api/jobs/{id}/subtitles?format=ass"},
 "music": {"title": "…", "license_name": "…", "license_url": "…", "attribution": "…"},
 "final_duration_seconds": 18.5}
```

`subtitles` is null when the job has no captions or is not succeeded; `music` is null without a library track.

## GET /api/jobs/{id}/images/{image_id} (new)

Returns the uploaded photo (original media type) for the review screen and job details. `404` for
another user's job or an expired job.

## PATCH /api/jobs/{id}/captions (new)

Requires CSRF. Only in `awaiting_review` (FR-064).

Request: `{"captions": [{"position": 0, "caption": "edited text"}]}` (partial list allowed).

- `200`: updated `Job`. Edited scenes get `caption_source: "user"`.
- `409 not_in_review` (message: captions can be edited only while the job is awaiting review)
- `422 caption_too_long` (names the position and the 2 × 42 limit)
- `422 unknown_position`

## POST /api/jobs/{id}/confirm (new)

Requires CSRF. Moves `awaiting_review` → `queued` and enqueues generation.

- `200`: `Job` with `status: "queued"`.
- `409 not_in_review`.

## POST /api/jobs/{id}/cancel and DELETE /api/jobs/{id} (changed)

Both now also accept `drafting` and `awaiting_review` jobs. `DELETE` still returns `409 job_running` for
`queued`/`running`.

## GET /api/jobs/{id}/subtitles?format=srt|ass (new)

- `200` `text/plain; charset=utf-8` (`application/x-subrip` or `text/x-ssa` as `Content-Type` hint
  allowed), `Content-Disposition: attachment; filename="movie-{id}.srt|.ass"`.
- `409 not_ready` before success; `404 no_subtitles` when captions were off; `404 not_found` for
  ownership/expiry; `422 invalid_format`.

## GET /api/capabilities (new)

Authenticated. Tells the client which optional services this server has, so the UI never guesses.

- `200`: `{"text_assist_available": bool, "music_library_available": bool}`.
  `text_assist_available` is true when an Anthropic credential is configured for caption drafting;
  `music_library_available` is true when `library.json` has at least one track. No model names, keys,
  or file paths are returned.

## GET /api/music (new)

Authenticated. `200`: `[{"id", "title", "mood", "duration_seconds", "license_name", "license_url", "attribution"}]`.
Empty list when the library is empty (research R10).

## GET /api/jobs/{id}/events (changed)

- `progress` events now carry `drafting` and `awaiting_review` statuses.
- New `event: review`, `data: {"status": "awaiting_review"}`, then the stream closes. Clients reconnect
  after `confirm`.
- `done` is unchanged (terminal statuses only).

## Contract tests to add

| Test | Expectation |
|------|-------------|
| Create with captions=false and no new fields | Same response and final video properties as 001 |
| Create with captions=true | `201` status `drafting`; reaches `awaiting_review` without any shot generated |
| PATCH captions in review | `200`, `caption_source=user`; same call after confirm → `409 not_in_review` |
| Confirm | `queued`; generation task enqueued once (idempotent second call → `409`) |
| Slideshow with no photos | `422 provider_needs_photos` |
| Subtitles download | SRT cues match `scenes[].start_seconds` ± 0.1 s (SC-010) |
| Audio upload rules | wrong type `400`, > 30 MB `413`, both bgm and bgm_id `422` |
| Consent missing | No request reaches the fake text assistance client; captions are verbatim |
| Ownership | Every new route returns `404` for another user's job |
