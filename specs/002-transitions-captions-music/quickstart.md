# Quickstart Validation: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Plan**: [plan.md](plan.md) | **Contracts**: [rest-api.md](contracts/rest-api.md), [video-provider.md](contracts/video-provider.md)

Runnable scenarios that prove the feature works end to end without a GPU. Field names and responses
are defined in the contracts; they are not repeated here.

## Prerequisites

- Feature 001 quickstart works (server, Redis, client build). See
  [specs/001 quickstart.md](../001-movie-video-generation/quickstart.md).
- FFmpeg with libass: `ffmpeg -hide_banner -filters` lists `subtitles`, `xfade`, `acrossfade`,
  `zoompan`, `loudnorm` (research VERIFY 1).
- `server/assets/fonts/` contains Noto Sans KR; `server/assets/music/library.json` exists (may be empty).
- Optional: `ANTHROPIC_API_KEY` (or another Anthropic credential) for assisted captions. Without it,
  captions are verbatim and every scenario below still passes except step 5's tone check.

## Run

```bash
fastapi dev --port 8000
celery -A server.worker.celery_app worker -Q generation --pool=solo --concurrency=1 -l info
celery -A server.worker.celery_app worker -Q planning   --pool=solo --concurrency=1 -l info
```

## Automated checks

```bash
ruff check . && ruff format --check . && mypy server tests
pytest tests/unit -k "timeline or subtitles or compose or audio or captions or cards or render_options" -v
pytest tests/contract -v                     # includes slideshow
pytest tests/integration -k "transitions or caption_review or subtitles or bgm or slideshow or text_assist" -v
```

Expected: all pass. The integration suite uses the slideshow and mock providers and a fake text
assistance client.

## Manual scenarios

1. **Defaults unchanged (FR-041)**: create a photos-only job with 3 photos, provider `mock`, no new
   options. Expected: status goes straight to `queued`; the final video has the same scene count and
   total length as on feature 001 (3 × 5 s = 15 s), one frame size, no audio stream.
2. **Transitions (US1)**: same photos, provider `slideshow`, transition `fade`, 1.0 s. Expected:
   video length 15 − 2 × 1.0 = 13 s (± 0.1 s); visible fades at 4 s and 8 s; `scenes[].start_seconds`
   = 0, 4, 8.
3. **Mixed sizes (FR-013)**: one job whose scenes come from photos of different aspect ratios.
   Expected: one frame size equal to the job's width × height; letterboxing, no stretching.
4. **Slideshow needs photos (US5)**: scenario-only job with provider `slideshow`. Expected:
   `422 provider_needs_photos` with a text message; nothing queued.
5. **Captions and review (US2, FR-064)**: 3 photos with notes, `captions=true`, tone `emotional`,
   consent on. Expected: `drafting` → `awaiting_review` within 60 s (SC-015); no shot files exist yet.
   Edit caption 2, confirm. Expected: `queued` → `succeeded`; the subtitle file shows caption 2 exactly
   as typed; captions 1 and 3 contain no facts beyond their notes (SC-011 spot check).
6. **Keyboard and screen reader (SC-014)**: complete step 5 using only the keyboard; each caption input
   is announced with its scene number and remaining characters; confirm is reachable by Tab.
7. **No consent**: repeat step 5 with consent off. Expected: captions equal the notes (wrapped to two
   lines); the planning worker log shows no outbound text assistance request.
8. **Subtitles and cards (US3)**: add title and ending, `burn_captions=true`, position bottom.
   Expected: video starts and ends with 3 s cards; captions are drawn in the lower part; SRT and ASS
   download; cue starts equal scene starts adjusted by half the transition (± 0.1 s, SC-010).
9. **Music (US4)**: upload a 10 s MP3 for a 20 s video, volume 0.3. Expected: music repeats, fades in
   and out, overall loudness about −14 LUFS (`ffmpeg -i final.mp4 -af ebur128 -f null -`); a 31 MB file
   is rejected with `413 audio_too_large`.
10. **Performance (SC-012)**: compare total time of step 2 with and without captions/music/transitions;
    the difference must be ≤ 10%, not counting review wait time.
11. **Retention**: after the retention sweep runs past `expires_at`, the job's subtitles and uploaded
    audio are gone together with its other media.
