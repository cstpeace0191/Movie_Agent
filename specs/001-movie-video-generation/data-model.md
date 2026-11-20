# Data Model: Movie Video Generation from Scenario and Photos

**Date**: 2026-11-20 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Entities come from the spec's Key Entities section, plus `Session` for login (R10). All timestamps are
UTC ISO 8601. All IDs are UUID v4 strings.

## Entity Relationships

```text
User 1 ──< Session
User 1 ──< Job 1 ──< SourceImage
                 1 ──< Scene 1 ──? SourceImage   (scene may use one photo)
                 1 ──< Shot  ──? Scene           (shot is generated for one scene)
                 1 ──? final_video (file reference)
```

## User

| Field | Type | Rules |
|-------|------|-------|
| id | UUID | Primary key |
| username | string | Unique, 3–32 chars, letters/digits/underscore, case-insensitive uniqueness |
| password_hash | string | argon2id hash; never returned by any API |
| created_at | datetime | Set on creation |

Owns: Session, Job. A user sees only their own jobs (FR-030, FR-031).

## Session

| Field | Type | Rules |
|-------|------|-------|
| token_hash | string | SHA-256 of the random session token; the raw token is only in the cookie |
| user_id | UUID | FK to User |
| csrf_token | string | Random; required in a header for POST and DELETE |
| created_at | datetime | |
| last_seen_at | datetime | Updated on use; session expires 7 days after this (R10) |

## Job

The central entity. Maps to spec **Job**.

| Field | Type | Rules |
|-------|------|-------|
| id | UUID | Primary key; returned to the client on creation (FR-024) |
| owner_id | UUID | FK to User; required; every query filters on it (FR-031) |
| input_mode | enum | `TEXT_ONLY`, `IMAGE_ONLY`, `TEXT_IMAGE` (spec section 1.2), derived from inputs |
| scenario | text | Optional. Non-empty if present. Stored as submitted. |
| status | enum | `queued`, `running`, `succeeded`, `failed`, `expired` (see transitions) |
| progress | int | 0–100 inclusive (FR-018) |
| message | string | Short plain-language stage message (≤ 200 chars) |
| failure_reason | string | Set when failed; names the failed shot when applicable (FR-027) |
| width | int | Default 832. Positive. Engine constraints to verify: [research.md](research.md), Verification item 6. |
| height | int | Default 480. Positive. |
| seconds_per_shot | float | Default 5. Range 5–10 (spec assumptions). |
| fps | int | Default 16. Positive. |
| chain_frames | bool | Default true (FR-015). |
| provider | string | Optional; defaults to server setting `VIDEO_PROVIDER`. One of `ltx-2.3`, `gemini-omni-1.2-flash`, `mock` (FR-035). |
| external_consent_at | datetime | Set when a cloud provider is chosen and the user confirms FR-036. Null for local engines. Kept as the audit record. |
| planned_seconds | float | Derived: shot count × seconds_per_shot. Must be ≤ 180 (FR-032). |
| final_video_path | string | Set on success; null otherwise. |
| created_at | datetime | |
| updated_at | datetime | |
| expires_at | datetime | created_at + 2 days (FR-034) |

**Validation (on creation)**:
- At least one of `scenario` or ≥ 1 SourceImage is present (FR-002), else 400.
- SourceImage count ≤ 100 (FR-004), else 400.
- `planned_seconds` ≤ 180 (FR-032), else 422 with the limit and planned length in the message.

**Job state transitions**:

```text
queued ──start──> running ──all shots + join ok──> succeeded
                     │
                     └──shot failed after retry──> failed
queued/running ──time limit exceeded (FR-025)──> failed
succeeded/failed ──retention (FR-034)──> expired
```

- `expired` jobs keep their row but have no media; download returns 404 (R12).
- `progress` is monotonic within a run; it returns to 0 only on a new submission.

## Scene

One part of a scenario, in order. Maps to spec **Scene**.

| Field | Type | Rules |
|-------|------|-------|
| id | UUID | |
| job_id | UUID | FK to Job |
| position | int | 0-based, unique within the job, contiguous (FR-005) |
| description | text | Visual description used as the engine prompt; non-empty (FR-005) |
| duration_seconds | float | Set to the job's seconds_per_shot unless the splitter provides a value within 5–10 |
| source_image_id | UUID | Optional FK to SourceImage, by position mapping (FR-008) |
| split_method | enum | `llm`, `paragraph`, or `photo_only` (FR-006, FR-011) |

**Invariant**: no part of the scenario is dropped (FR-007). Concatenated scene descriptions cover all
non-empty paragraphs of the input.

## Shot

The generated clip for one scene. Maps to spec **Shot**.

| Field | Type | Rules |
|-------|------|-------|
| id | UUID | |
| job_id | UUID | FK to Job |
| scene_id | UUID | FK to Scene; one shot per scene (FR-012) |
| position | int | Matches scene position |
| status | enum | `pending`, `running`, `succeeded`, `failed` |
| attempts | int | 0–2. Retry allowed once (FR-033), so a shot is attempted at most twice. |
| source_frame_from | UUID | Optional: shot whose last frame feeds this shot (chain_frames, FR-009) |
| clip_path | string | Set on success |
| error | string | Last error, plain language; set on failure |

**Transitions**: `pending → running → succeeded`, or `running → (retry, attempts=2) → running → failed`.
A job fails when any shot reaches `failed` (FR-033).

## SourceImage (Photo)

An uploaded photo. Maps to spec **Photo (Source Image)**.

| Field | Type | Rules |
|-------|------|-------|
| id | UUID | |
| job_id | UUID | FK to Job; belongs to one job |
| position | int | 0-based upload order; maps to scene `position` (FR-008) |
| original_filename | string | Stored for display only; never used as a file path |
| media_type | enum | `image/jpeg`, `image/png`, `image/webp` (FR-003) |
| size_bytes | int | ≤ 20 × 1024 × 1024 (FR-003) |
| storage_path | string | Server-generated path; never derived from the filename |
| alt_text | string | Optional, ≤ 500 chars (constitution Principle III) |
| used | bool | False when the photo is unused (FR-010), so the user can be told |

**Validation**: magic bytes must match `media_type`, not only the extension or the client header. A file
that fails the check is rejected with a message naming the file (edge case in spec).

## Derived rules

- `input_mode`: `TEXT_ONLY` if no photos; `IMAGE_ONLY` if no scenario; `TEXT_IMAGE` if both.
- Photo-only shot count = number of photos (FR-011). Scenario shot count = number of scenes. Both-input shot
  count = number of scenes, with unused photos reported (FR-010) or the last photo reused (FR-009).
- `planned_seconds` is computed from the shot count before any generation starts.
