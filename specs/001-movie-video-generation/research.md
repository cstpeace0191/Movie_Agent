# Research: Movie Video Generation from Scenario and Photos

**Date**: 2026-11-20 | **Plan**: [plan.md](plan.md)

**Method**: Decisions below come from `spec.txt` (sections 1 to 9), the clarifications in `spec.md`, the
project constitution, and web research on 2026-11-20. Items marked **VERIFY** must be checked against
current official sources before they are adopted (see the final section).

## R1. Default local video engine

**Decision**: LTX-2.3 (Lightricks) is the default local engine on the NVIDIA GeForce RTX 4090 (24 GB VRAM). It
replaces the earlier Wan choice, as directed by the user on 2026-11-20. It runs through the ComfyUI API, which
secondary guides say supports LTX-2.3 (VERIFY item 5).

**Rationale**:
- The official Hugging Face model card (Lightricks/LTX-2.3) tags the model for text-to-video and
  image-to-video. Both modes are needed (spec section 1.2).
- Checkpoints: `ltx-2.3-22b-dev`, `ltx-2.3-22b-distilled`, `ltx-2.3-22b-distilled-1.1`.
- **VRAM is the main risk.** A 22B-parameter model in bf16 needs about 44 GB for weights alone (22B × 2 bytes),
  which exceeds the 4090's 24 GB. The card recommends bf16 for the dev model. Running on the 4090 therefore
  requires an FP8 checkpoint or CPU/disk offloading. Secondary sources report FP8 runs on the 4090, but these
  are not official (VERIFY item 2).
- Speed: a secondary report gives about 4 to 6 minutes per 10-second 1080p clip on an RTX 4090. This conflicts
  with the 30-minute budget for a 36-shot job in plan Technical Context (VERIFY item 3).

**License (blocks adoption until read)**:
- The LTX-2 code repository (`Lightricks/LTX-2` on GitHub) is Apache 2.0. That covers the code only.
- The model weights are under `ltx-2-community-license-agreement`, per the Hugging Face model card. The
  license file URL on Hugging Face returned 404, so the terms could not be read.
- Secondary sources say free use is allowed below $10M annual revenue and that larger use needs an enterprise
  license. This is unconfirmed. Territorial limits are also unknown. The constitution forbids a default model
  that restricts use in Korea, so this must be checked (VERIFY item 1).

**Alternatives considered**:
- Wan 2.2 (Apache 2.0, released 2025-07-28): the most recent verified permissive open-weights Wan release. It
  is the fallback if the LTX-2.3 license is unacceptable. The user directed a move away from Wan for the default.
- Gemini Omni 1.2 Flash: a cloud option, not a local default. See R15.
- HunyuanVideo: rejected. Its license excludes use in Korea (spec section 2.1).

## R2. Video engine abstraction and per-job selection

**Decision**: A `VideoProvider` protocol with one method, `generate(request) -> result`, plus a typed error
(transient vs. permanent). Three provider keys exist: `ltx-2.3` (local GPU, default), `gemini-omni-1.2-flash`
(cloud), and `mock` (development and tests only). The server default comes from the `VIDEO_PROVIDER`
environment variable. Each job can choose a provider in the UI, from the list returned by `GET /api/providers`.
Details: [contracts/video-provider.md](contracts/video-provider.md).

**Rationale**: Spec section 1.3 requires engine swaps through configuration (FR-016, SC-008). The user also
asked for a front-end choice between LTX-2.3 and Gemini (FR-035). Every failed shot is retried once (FR-033). The
transient flag only sets the message and the log level, so the error type stays part of the contract.

**Alternatives considered**: Engine-specific code paths in the worker (rejected: violates FR-016 and the
constitution's engine rule); a plugin registry (rejected: more machinery than three providers need); choosing
the engine only by server configuration (rejected: the user asked for a per-job choice).

## R3. Development engine

**Decision**: `mock` provider writes FFmpeg-generated test clips (solid color plus text overlay of shot number).

**Rationale**: Spec section 6 requires full-flow validation without a GPU. Deterministic output makes
integration tests assert exact shot counts and durations.

## R4. Background jobs and GPU concurrency

**Decision**: Celery 5 with Redis as the broker. The GPU worker runs with concurrency 1 (`--pool=solo` on
Windows dev). Celery beat runs the retention sweep (R12). Cloud jobs use the same queue, so they also run one
at a time per worker (simpler, and it keeps the time limit in one place).

**Rationale**: FR-024 (background work), FR-026 (one job at a time per GPU), FR-025 (time limits per task),
and beat scheduling for FR-034 all map to built-in Celery features. Spec section 7 already chooses this.

**Alternatives considered**: RQ or arq (simpler, but no built-in beat-style scheduling and weaker time-limit
handling); in-process background threads (rejected: no crash recovery and no GPU isolation); a separate queue
for cloud jobs (deferred: adds complexity that five users do not need).

## R5. Progress delivery

**Decision**: Progress is written to the database at each stage and each shot change. The browser receives
updates over Server-Sent Events (SSE), with a heartbeat at least every 10 s.

**Rationale**: SSE is one-way (server to browser), which matches progress. It works over plain HTTP, and
the browser's `EventSource` reconnects automatically. Writing to the database lets progress survive a page
reload or a dropped connection (FR-020).

**Alternatives considered**: WebSockets (bidirectional, not needed; more infrastructure); polling every
few seconds (simpler, but adds load and latency; kept only as a fallback if SSE is blocked).

## R6. Scene splitting

**Decision**: An LLM call (Anthropic SDK, `claude-haiku-5-5`, set by user decision on 2026-11-20; spec section 7
named `claude-opus-5-5`) returns scenes as JSON with `prompt` and `duration`. Narration is out of scope for this release. If the key
is missing, the call fails, or the output does not validate, the paragraph-based split runs instead (FR-006).

**Rationale**: The LLM gives better shot prompts. The rule-based fallback keeps every job completing
(FR-006, F-03). Validating the output before use prevents a malformed model reply from killing a job.

**Alternatives considered**: Rules only (cheapest, but weak shot prompts); a local Qwen via vLLM or Ollama
(no per-call cost, but another GPU workload that competes with video generation on the 4090).

**Resolved**: model is `claude-haiku-5-5`. Output quality on sample scenarios is still to be checked.

## R7. Text-only shots in the first release

**Decision**: Text-only jobs use text-to-video (T2V) for every shot in the first release. Keyframe images
(FLUX) are deferred to Phase 2 of the roadmap.

**Rationale**: LTX-2.3 supports text-to-video (model card tags), so the keyframe step is not needed to deliver
the MVP. The spec's Phase 1 scope (section 9) lists "T2V/I2V" without FLUX.

**Impact**: Spec section 1.2 describes TEXT_ONLY as keyframe generation followed by T2V or I2V. For the MVP,
the keyframe step is skipped. This is a deliberate narrowing, and the tasks phase should note it.

## R8. Media processing

**Decision**: FFmpeg called directly (subprocess with argument lists, never shell strings) for
normalization (scale, pad, fps), last-frame extraction for chained shots (FR-009, `chain_frames`), and
concatenation into `final.mp4`.

**Rationale**: FFmpeg is required by spec section 2.2. Calling it directly keeps dependencies small and
the behavior explicit. MoviePy adds a second layer without a clear benefit here.

**Alternatives considered**: MoviePy (extra dependency, slower, less control over codec flags); MLT (heavier
than needed).

## R9. Storage and database

**Decision**: MySQL 9.3 for Docker/production deployment (with SQLite fallback for local testing) and local disk for media in the first release. Both sit behind
SQLAlchemy and a storage interface, with PyMySQL driver for MySQL connectivity.

**Rationale**: MySQL 9.3 provides robust ACID compliance, structured relational data handling, and containerized deployment with healthcheck verification.

**Alternatives considered**: SQLite-only (insufficient for concurrent multi-container production environments), PostgreSQL and MinIO now (more operations for a small user base, with no
measured need).

## R10. Authentication (login method deferred to planning by clarification)

**Decision**: Username and password. Passwords are hashed with argon2id (`argon2-cffi`). Sessions are
random 256-bit tokens stored server-side in the database. The session cookie is `HttpOnly` and
`SameSite=Lax`, and has `Secure` when served over HTTPS. Sessions expire after 7 days of inactivity (proposed
default). State-changing requests (POST, DELETE) require a CSRF token in a header.

**Rationale**: FR-030 requires login. Server-side sessions can be revoked at once, which JWTs cannot do
simply. Argon2id is the current recommended password hash.

**Alternatives considered**: OAuth2/OIDC with an external provider (rejected for the first release: adds an
external dependency and account setup for ≤ 5 users; can be added later); JWT in local storage (rejected:
harder to revoke and exposes the token to scripts).

## R11. Ownership and privacy

**Decision**: Every job, shot, and video query filters on the owner's user ID. A request for another
user's resource returns 404, identical to a missing resource.

**Rationale**: FR-031 forbids revealing another user's jobs or their existence. Returning 403 would reveal
existence, so 404 is required.

## R12. Retention

**Decision**: Celery beat runs `expire_old_jobs` hourly. It deletes media files (photos, shots, final video)
for jobs whose `expires_at` (creation time + 2 days) has passed, and sets the job status to `expired`.
Job rows are kept (see plan Open Decisions).

**Rationale**: FR-034 requires automatic, permanent deletion. An hourly sweep means media lives at most
about 2 days and 1 hour. Keeping job rows keeps the list accurate. Cloud-engine output is also deleted from our
storage on this schedule. The provider's own retention is separate (R15, VERIFY item 4).

## R13. Accessibility and Client Implementation

**Decision**: React with TypeScript (built with Vite) served by the API. Semantic elements (`form`, `label`,
`button`, `table` for the shot list, `fieldset` and `legend` for the engine choice). An `aria-live="polite"`
region announces progress changes. Errors are text in an `role="alert"` region. `axe-core` runs in tests.

**Rationale**: React with TypeScript provides type safety for API models, structured state management for live progress
and dynamic photo alt-text fields, and reusable accessible components. Semantic HTML elements inside React JSX
guarantee keyboard and screen-reader access without accessibility loss. Live regions announce progress without stealing focus.

**Alternatives considered**: Plain Vanilla JS (initially considered for zero build tooling, but React TypeScript adopted for type safety and component maintainability).

## R14. Code quality tooling

**Decision**: ruff (lint and format), mypy (type checks on `server/` and `tests/`), pytest (tests).
Configured in the root `pyproject.toml`.

**Rationale**: Constitution Principle I requires these tools for the Python code.

## R15. Cloud engine: Gemini Omni 1.2 Flash

**Decision**: Gemini Omni 1.2 Flash (model ID `gemini-omni-1.2-flash`) is a per-job option in the UI. It is not
the default. It is called through the Gemini API.

**Verified on Google's AI Studio pricing page (2026-11-20)**:
- Status: generally available on the paid tier. No free tier is listed.
- Output price: $12.00 per 1M video output tokens. Billing uses 5,792 output tokens per second of 720p video,
  which is about $0.07 per second. Other resolutions: 360p about $0.023/s, 1080p about $0.104/s, 4K about $0.209/s.
- Maximum clip length: 15 seconds, with native audio. The 5 to 10 second shots (spec assumptions) fit.
- Cost example: a 3-minute 720p job costs about $12.50 in generation alone.
- Gemini Omni 1.1 Flash routes to 1.2 from December 3, 2026, billed at 1.2 rates.

**Privacy**: Choosing this engine sends the scenario text and uploaded photos to Google. FR-036 requires a
disclosure and an explicit confirmation for each job. Google's retention and training terms for the paid tier
were not verified (VERIFY item 4). Third-party hosts (AI/ML API, Segmind, Runware) were not used, because they
would add another party that receives user data.

**Rationale**: It needs no local GPU, so it covers jobs that are too slow or too large for the 4090 and users
who prefer it. It accepts text and images, so it covers both input modes.

**Alternatives considered**: Gemini Omni 1.1 Flash (superseded by 1.2 on December 3, 2026); the earlier
`gemini-omni-flash-preview` (shut down, per secondary sources).

## Verification Required Before Adoption (VERIFY)

These items were not fully checked against official sources during planning. Each must be verified in the tasks
phase before the decision is treated as final.

1. **VERIFY (blocks local-default adoption)**: LTX-2.3 weights license. Read the full
   `ltx-2-community-license-agreement`. Confirm commercial use, the revenue threshold, any enterprise-license
   requirement, and any territorial restriction (including Korea). If it is not acceptable, the default moves to
   Wan 2.2 (Apache 2.0). The Hugging Face LICENSE URL returned 404, so the text must be obtained another way
   (for example, the model's GitHub repository or the Lightricks site).
2. **VERIFY (blocks local-default adoption)**: LTX-2.3 precision and VRAM on the RTX 4090. Confirm an official
   FP8 checkpoint or an offloading path exists and is supported by ComfyUI. Measure peak VRAM at 832×480,
   16 fps, 5 s shots.
3. **VERIFY (blocks the performance budget)**: Generation time per shot on the RTX 4090. Measure a full 36-shot
   job. If it cannot meet the 30-minute budget in plan Technical Context, the budget or the 3-minute cap (FR-032)
   must be revisited. The budget is not relaxed silently.
4. **VERIFY (blocks enabling the cloud option)**: Gemini Omni 1.2 Flash data handling for the paid API: retention
   period, and whether input is used for training. Also re-check pricing and the December 3, 2026 routing change
   on Google's official pages before launch. The figures above come from Google's AI Studio pricing page, which
   was read directly.
5. **VERIFY**: ComfyUI workflow JSON for LTX-2.3 (`workflows/ltx_t2v.json`, `workflows/ltx_i2v.json`) and the
   node names it uses.
6. **VERIFY**: `claude-haiku-5-5` pricing and quality on sample scenarios. The model ID comes from the project's
   model list and was not checked on the web.
7. **VERIFY**: Celery 5 `--pool=solo` behavior with time limits on Windows.
8. **VERIFY**: Width and height constraints of LTX-2.3 and Gemini Omni (for example, multiples of 32 or 16).
   These affect validation of the resolution option.

**Sources read on 2026-11-20**:
- Lightricks/LTX-2.3 Hugging Face model card (official, read directly)
- Google AI Studio pricing page, `aistudio.google.com/docs/pricing` (official, read directly)
- LTX-2 GitHub LICENSE, `github.com/Lightricks/LTX-2` (Apache 2.0, code only)
- Secondary: search summaries for LTX-2.3 VRAM and speed, and for Gemini Omni API pricing. These are
  inconsistent and treated as unverified.
