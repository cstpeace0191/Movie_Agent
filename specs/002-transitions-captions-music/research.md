# Research: Scene Transitions, Photo Captions, Subtitles, and Background Music

**Date**: 2026-11-21 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Each item records Decision, Rationale, and Alternatives considered. Items marked **VERIFY** must be
checked on the target machine before the related task is closed; none blocks planning.

## Findings from the current code (inputs to the decisions below)

- `server/worker/pipeline/join.py` joins with the concat demuxer and stream copy, falling back to a
  re-encode without scaling. Clips of different size or fps are not normalized (FR-013 gap).
- `server/app/api/jobs.py` splits scenarios with `split_by_paragraphs` at submission.
  `split_with_llm` (Claude) exists but is not called by any route, so today no scenario text is sent to
  an external text service. FR-046 therefore only needs to gate the new caption drafting (and any future
  use of `split_with_llm`).
- The mock provider writes video without an audio stream; real engines may write audio.
- The schema is created with `Base.metadata.create_all`, plus an ad-hoc `ALTER TABLE ... ADD COLUMN`
  helper in `db.py` (used for `users`). There is no Alembic.
- The SSE endpoint ends the stream only on `succeeded`/`failed`.

## R1. Timeline computation

**Decision**: A pure function `build_timeline(scenes, transition_default, transition_seconds) ->
Timeline` in `pipeline/timeline.py`. Inputs are measured clip lengths (from probing, not requested
lengths) and per-scene transition overrides. Rules from specify.txt §6.1: `t_i = min(T, d_{i-1}/2,
d_i/2)`, `s_i = s_{i-1} + d_{i-1} - t_i`, total `= Σd - Σt`; `auto` cycles a fixed ordered list so
neighbours differ. Results are written to `Scene.start_seconds` / `Scene.length_seconds`.

**Rationale**: One source of truth for time keeps subtitle cues (SC-010) and xfade offsets consistent,
and a pure function is cheap to test exhaustively (constitution II).

**Alternatives**: Computing offsets inside the FFmpeg command builder (rejected: subtitles would
recompute time separately and drift); relying on requested durations (rejected: engines may return
shorter clips).

## R2. Joining and normalization

**Decision**: `pipeline/compose.py` builds one `filter_complex`: per input
`scale=W:H:force_original_aspect_ratio=decrease,pad=W:H:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=F,
format=yuv420p,trim=duration=d_i,setpts=PTS-STARTPTS,settb=AVTB`, then a left fold that uses
`xfade=transition=<name>:duration=t_i:offset=s_i` when `t_i > 0` and `concat=n=2:v=1:a=<0|1>`
otherwise. Encode with `libx264 -preset veryfast -crf 20 -movflags +faststart`. `join.py` is deleted
when compose passes the feature 001 join tests plus the new ones.

**Rationale**: Fixes FR-013, makes "none" equal to the 001 result in scenes/order/length (FR-041), and
lets transitions mix with cuts per scene. Trade-off: 001 usually joined by stream copy (seconds);
compose always re-encodes. For a 3-minute 832×480 video at `veryfast` this is expected to stay well
under the 60 s compose budget, and SC-012 measures it.

**Alternatives**: Keep concat demuxer for "none" and a separate path for transitions (rejected: two
code paths, and the demuxer path still skips normalization); MoviePy (rejected: slower, extra
dependency, still calls FFmpeg).

## R3. Transition names

**Decision**: Map spec names to built-in `xfade` transitions: fade→`fade`, fade through black→`fadeblack`,
fade through white→`fadewhite`, dissolve→`dissolve`, slide left/right/up/down→`slideleft`/`slideright`/
`slideup`/`slidedown`, wipe left→`wipeleft`, circle open→`circleopen`, zoom in→`zoomin`. `auto` cycles
`fade, slideleft, dissolve, wipeleft, circleopen, slideup`. The API stores the spec-level identifiers
(`fade`, `fade_black`, …) and the mapping lives only in `compose.py`.

**Rationale**: All are standard `xfade` names (FFmpeg ≥ 4.3), so no custom shaders are needed.

**Alternatives**: Custom `xfade=custom` expressions (rejected: harder to test, no user value now).

## R4. Audio handling

**Decision**: `pipeline/audio.py` probes each clip for an audio stream. If no clip has audio and no
music is chosen, the output has no audio stream (FR-051). Otherwise every clip without audio gets a
generated silent track (`anullsrc`, matched length) so all inputs have audio; audio joins use
`acrossfade=d=t_i` where video uses xfade and `concat` elsewhere. Music: `-stream_loop -1` input,
`atrim=duration=T`, `afade=t=in:d=1`, `afade=t=out:st=T-2:d=2`, `volume=v`, then `amix` with the scene
audio (`normalize=0`), then `loudnorm=I=-14:TP=-1.5:LRA=11` (single pass). Encode AAC 160 kb/s.

**Rationale**: Keeps engine audio (spec assumption), guarantees fades and repeat (FR-050), and gives
one consistent loudness. Single-pass loudnorm is accurate enough for short videos and keeps compose
within its budget.

**Alternatives**: Two-pass loudnorm (rejected for now: doubles audio processing; revisit if measured
loudness deviates by more than 1 LU); dropping engine audio when music is chosen (rejected: contradicts
the spec assumption).

## R5. Subtitles and burn-in

**Decision**: `pipeline/subtitles.py` writes SRT (UTF-8, no BOM) and ASS from the timeline. Cue i spans
`[s_i + t_i/2, s_{i+1} + t_{i+1}/2)`, last cue to T; title/ending cards have no cue. ASS style: font
Noto Sans KR (bundled in `server/assets/fonts/`, OFL), size from `caption_size`
(small/medium/large → 4%/5.5%/7% of frame height), primary colour from `caption_color`, black outline
3 px with shadow 1, `BorderStyle=3` (opaque box at 60% black) when `caption_box=true`; alignment 2
(bottom) or 8 (top). Automatic position = bottom in this release (no face detection; see R12). Burn-in
uses the `subtitles=subtitles.ass:fontsdir=<assets/fonts>` filter as the last video filter. Lines are
wrapped at 42 characters, max two lines.

**Rationale**: SRT and ASS are the formats named in the spec; outline + box guarantee ≥ 4.5:1 against
any background; bundling the font makes Korean rendering independent of the host.

**VERIFY 1**: the FFmpeg in `Dockerfile` and on the dev machine is built with `--enable-libass`
(`ffmpeg -filters | grep subtitles`). If the static `imageio-ffmpeg` binary lacks it, install a distro
FFmpeg in the image.

**VERIFY 1 result (2026-11-21, T005)**: Dev machine (Windows) has no FFmpeg on PATH; the pipeline
now falls back to the `imageio-ffmpeg` 0.8.1 bundled binary (FFmpeg 9.0.2). Its `-filters` list has
`subtitles`, `ass`, `xfade`, `acrossfade`, `zoompan`, `loudnorm`, `drawtext`, and its build config has
`--enable-libass --enable-libfreetype --enable-libharfbuzz --enable-fontconfig`. The Docker image
installs Debian's `ffmpeg` package, which is normally built with libass, but the image was not built
and checked in this run.

**Alternatives**: `drawtext` per caption (rejected: no ASS styling reuse, fragile escaping of Korean
text); WebVTT (deferred: easy to add from the same cue list).

## R6. Caption drafting with the text assistance service

**Decision**: `pipeline/captions.py` sends one request per chunk of up to 20 scenes with the Anthropic
Python SDK. Model is set by `CAPTION_MODEL` (default `claude-opus-5-5`); the request uses the SDK's
structured-output parsing with a Pydantic schema `{captions: [{position:int, caption:str,
narration:str}]}`, `output_config.effort="low"` (short, simple writing), and server-side refusal
fallbacks (`betas=["server-side-fallback-2026-07-01"]`, `fallbacks="default"`). Each photo is
downscaled with Pillow to ≤ 1024 px on the long edge, JPEG quality 85, and sent as a base64 image
block with its note/alt text. The prompt states the tone, the two-line/42-character limit, the
language rule (write in the language of the note/scenario), and that no fact may be added beyond the
inputs. On any API error, `refusal` stop reason, schema failure, missing consent, or missing API key,
the caption is the note (else alt text, else scene text) wrapped to two lines with an ellipsis
(FR-045 fallback). The client is constructed once per worker process.

**Rationale**: One request per 20 scenes meets SC-015 (≤ 60 s) and stays far below request-size limits;
low effort suits short captions; fallbacks and the verbatim path ensure the job never fails because of
captioning (FR-045, same principle as FR-006). Model choice is configuration, so the team can switch to
the cheaper `claude-haiku-5-5` (already used by `split_with_llm`) after measuring caption quality
against SC-011, without code changes.

**VERIFY 2**: confirm the exact structured-output call (`client.messages.parse(...)` binding and
parameter names) against the installed `anthropic` SDK version before writing `captions.py`; upgrade
the pin in `pyproject.toml` if the installed version predates it.

**VERIFY 2 result (2026-11-21, T006)**: `uv.lock` pins `anthropic` 2.11.0. Checked by introspection:
`client.messages.parse` exists; `client.messages.create` accepts `output_config`;
`client.beta.messages.create` accepts `fallbacks`; `client.beta.messages.parse` exists. No pin change
is needed. The exact structured-output argument (`output_format=` on `parse`) is to be confirmed
against the SDK docs when `captions.py` is written (US2).

**Alternatives**: One request per photo (rejected: 100 requests for 100 photos, slower and costlier);
local VLM such as Qwen2.5-VL (deferred: needs GPU memory that LTX already uses); free-form text output
parsed with regex (rejected: brittle).

## R7. Review flow and job states

**Decision**: New statuses `drafting` and `awaiting_review`. Submission with captions on →
`drafting` (job row created, `draft_captions_task` sent to the `planning` queue) → `awaiting_review`
→ `POST /api/jobs/{id}/confirm` → `queued` (generation task sent to the `generation` queue) →
`running` → `succeeded`/`failed`. Captions off → `queued` directly (001 behaviour). Drafting failure
falls back to verbatim captions and still reaches `awaiting_review`. State changes are conditional
updates (`UPDATE ... WHERE status = <expected>`): the drafting task moves a job to `awaiting_review`
only if it is still `drafting` (a job cancelled or deleted meanwhile stays cancelled, and its drafts
are discarded), and confirm moves a job to `queued` only from `awaiting_review`, so a double click or a
second request cannot enqueue generation twice. Cancel and delete are allowed in
`drafting` and `awaiting_review`. Retention sweep treats both like any other status. SSE sends a
`review` event and closes when the job reaches `awaiting_review`; the client reconnects after confirm.

**Rationale**: Matches FR-064 (no generation before confirmation, no queue slot held while waiting) and
keeps the FR-026 queue order meaning "confirmed jobs in confirmation order".

**Alternatives**: Reusing `queued` for drafting (rejected: confuses queue position and cancellation
rules); keeping the SSE stream open while waiting (rejected: review can take days).

## R8. Celery queues

**Decision**: `task_routes` sends `draft_captions_task` to queue `planning` and `run_job` to queue
`generation`. Run two workers: `celery -A server.worker.celery_app worker -Q generation --pool=solo
--concurrency=1` (GPU) and `celery ... worker -Q planning --pool=solo --concurrency=1` (no GPU; threads
pool allowed on Linux). Retention and email tasks go to `planning`.

**Rationale**: See Complexity Tracking in plan.md. Keeps the GPU worker at concurrency 1 (FR-026).

**Alternatives**: Celery priorities on one queue (rejected: a running 30-minute task still blocks the
only process).

## R9. Photo slideshow provider

**Decision**: `providers/slideshow.py` renders `zoompan` at 2× output size then scales down
(reduces jitter): zoom in `z='min(zoom+k,1.25)'`, zoom out `z='if(eq(on,0),1.25,max(zoom-k,1.0))'`,
pans move `x`/`y` linearly across the 1.25× crop, with `k = 0.25/frames`. `ShotRequest` gains
`motion: str | None = None` (ignored by other providers). Provider classes gain class attributes
`requires_photos: bool` (slideshow `True`, others `False`) and `sends_data_externally: bool`. The API
reads these via the registry. A request without a source image raises a permanent `ProviderError`.

**Rationale**: GPU-free, deterministic, fast (≈ real-time encode at 832×480), and testable in CI.

**Alternatives**: Reusing the mock provider's image path (rejected: mock is development-only and hidden
in production); a Ken Burns library (rejected: unnecessary dependency).

## R10. Background music library and uploads

**Decision**: `server/assets/music/library.json` lists `{id, title, mood, duration_seconds, file,
license_name, license_url, attribution}`; `GET /api/music` serves it without file paths. Initial
library: 5–8 tracks from a source whose license allows redistribution inside user videos without per-video
attribution or with attribution shown on the result page. Uploads are validated by magic bytes: MP3
(`ID3` or frame sync `FF Fx`), WAV (`RIFF....WAVE`), M4A (`....ftypM4A ` / `ftypisom` with audio track
check via probe), size ≤ 30 MB, stored at `storage/jobs/<id>/audio/bgm.<ext>`.

**VERIFY 3**: choose the actual tracks and record each license text in `server/assets/music/LICENSES/`
before release. Until then the library ships empty and the UI hides the library list.

**Alternatives**: MusicGen (rejected: CC-BY-NC weights); streaming from an external music API
(rejected: external dependency and data disclosure).

## R11. Text assistance consent

**Decision**: New form field `text_assist_consent` (bool). When captions are on and the server has a
caption API key, the UI shows a text disclosure listing what will be sent (notes, alt text, scenario,
photos). The API stores `Job.text_assist_consent_at`. The worker sends nothing when it is null and uses
verbatim captions. `split_with_llm`, if wired into routes later, MUST check the same field.

**Rationale**: Mirrors FR-036 handling; keeps the decision per job, like engine choice.

**Alternatives**: Account-level consent (rejected for this release: needs settings UI and revocation
rules; can be added later without changing the per-job record).

## R12. Out of scope or deferred in this release

- Automatic caption position from face/subject detection: "automatic" resolves to bottom. Recorded so
  the UI labels it "Automatic (bottom)".
- EXIF GPS stripping (specify.txt §11.3): not in this feature's FRs; tracked for a follow-up.
- Card scenes: rendered by `cards.py` as solid-background clips with centred text in the same font,
  length 3 s each (counted in planned length, FR-049).

## R13. Schema changes

**Decision**: Add nullable columns through the existing `db.py` add-missing-columns helper, extended
to `jobs`, `scenes`, and `source_images`. Status remains a string column, so new values need no DDL.

**Rationale**: Consistent with how 001 evolved `users`; works on SQLite and MySQL.

**Alternatives**: Introduce Alembic now (deferred: worthwhile, but a cross-cutting change outside this
feature's scope).

## Post-design Constitution Check (re-evaluated after Phase 1)

| Gate | Result after design |
|------|---------------------|
| I. Code Quality | PASS. Contracts keep engine names inside providers; compose/timeline/subtitles have separate tests. |
| II. Test-First | PASS. Every contract change has listed tests (contracts/video-provider.md, contracts/rest-api.md). |
| III. Accessibility | PASS. Review screen and new controls specified with labels, keyboard order, and live announcements (quickstart step 6). |
| IV. Performance | PASS. Budgets measurable via quickstart steps 3 and 9; planning queue isolates SC-015. |
| Technical constraints | PASS. No default-engine change; licenses tracked for fonts and music. |
