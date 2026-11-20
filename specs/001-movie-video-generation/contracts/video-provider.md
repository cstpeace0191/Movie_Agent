# Contract: VideoProvider (engine interface)

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Research**: [R2](../research.md)

Every video engine implements this contract. The worker depends only on this contract, never on an engine
name (FR-016, SC-008, constitution technical constraint).

## Protocol

```python
class VideoProvider(Protocol):
    name: str  # "ltx-2.3", "gemini-omni-1.2-flash", or "mock"

    def generate(self, request: ShotRequest) -> ShotResult:
        """Generate one clip. Blocks until done or fails. Called from a worker only."""


@dataclass(frozen=True)
class ShotRequest:
    prompt: str  # scene description (required, non-empty)
    duration_seconds: float  # 5–10
    width: int
    height: int
    fps: int
    source_image_path: Path | None  # None for text-to-video (T2V)
    output_path: Path  # provider writes the clip here


@dataclass(frozen=True)
class ShotResult:
    clip_path: Path  # equals output_path on success
    duration_seconds: float  # measured from the file, not requested
    width: int
    height: int
    fps: int


class ProviderError(Exception):
    transient: bool  # True: transient failure; False: permanent. Both are retried once (FR-033)
    message: str  # plain language, shown to the user
```

## Mode selection (inside the provider, not the worker)

| `source_image_path` | Mode |
|---------------------|------|
| None | text-to-video (T2V) |
| set | image-to-video (I2V) |

The worker passes the previous shot's last frame as `source_image_path` when `chain_frames` is true (FR-009).

## Behavior rules

1. `generate` MUST write the clip to `output_path` only on success. A failed call leaves no partial file there.
2. `duration_seconds` and `fps` in the result MUST match the request within 0.1 s and 0 fps. A mismatch is a
   permanent `ProviderError`.
3. Transient errors (timeouts, engine busy, connection reset) set `transient=True`. Invalid input, missing
   model, and unsupported size set `transient=False`. The worker retries every failed shot once (FR-033).
   The flag only sets the message and the log level; it does not decide whether a retry happens.
4. The provider MUST NOT log or return secrets (API keys). Logs use the job and shot IDs.
5. A provider MUST respect the time limit from the worker. It MUST stop work when it receives cancellation (FR-025).
6. A cloud provider (`gemini-omni-1.2-flash`) MUST NOT receive any scenario text or image before the job's
   FR-036 confirmation is recorded. The worker checks this, and the provider also refuses to run without it.
7. A shot duration above the provider's maximum clip length is a permanent `ProviderError`. Gemini Omni's
   maximum is 15 seconds, which covers the 5 to 10 second shots in the spec.

## Provider configuration

| Setting | Source | Example |
|---------|--------|---------|
| `VIDEO_PROVIDER` | environment (`.env`) | server default: `ltx-2.3`, `gemini-omni-1.2-flash`, or `mock` |
| LTX-2.3 ComfyUI URL | environment | `LTX_COMFYUI_URL=http://127.0.0.1:8188` |
| Gemini API key (cloud only) | environment only | `GEMINI_API_KEY=...` (never committed) |

Per-job choice: a job may set `provider` to any enabled engine (see `GET /api/providers` in the REST contract).
`mock` is enabled only in development mode.

## Contract tests

One shared suite in `tests/contract/` runs against every provider. A provider cannot be merged until it
passes the suite (constitution Principle II).

| Test | Expectation |
|------|-------------|
| T2V request produces a clip | `clip_path` exists; duration, size, fps match the request |
| I2V request with an image | Same as above; output differs from a text-only run for the same prompt |
| Invalid duration (outside 5–10 s) | Raises `ProviderError`, `transient=False`, no file written |
| Missing source image path | Raises `ProviderError`, `transient=False` |
| Simulated timeout | Raises `ProviderError`, `transient=True`, no partial file |
| Failure mid-generation | No file at `output_path` |

The `mock` provider runs the full suite in CI without a GPU. The `ltx-2.3` provider runs it in a separate
GPU-gated integration job on the RTX 4090. The `gemini-omni-1.2-flash` provider runs it only when
`GEMINI_API_KEY` is set, and only in a manually triggered job, because each run has a cost.
