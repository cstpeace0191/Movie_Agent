# Contract Delta: VideoProvider (feature 002)

**Feature**: [spec.md](../spec.md) | **Plan**: [plan.md](../plan.md) | **Research**: [R9](../research.md)
**Base**: [specs/001 contracts/video-provider.md](../../001-movie-video-generation/contracts/video-provider.md).
All 001 rules still apply.

## Changes to the protocol

```python
class VideoProvider(Protocol):
    name: str
    requires_photos: bool  # NEW. True: cannot do text-to-video
    sends_data_externally: bool  # NEW (moves the 001 API-side flag onto the provider)

    def generate(self, request: ShotRequest) -> ShotResult: ...


@dataclass(frozen=True)
class ShotRequest:
    prompt: str
    duration_seconds: float
    width: int
    height: int
    fps: int
    source_image_path: Path | None
    output_path: Path
    motion: str | None = None  # NEW. zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down.
    # Resolved by the worker (auto -> concrete). Providers that do not
    # use it MUST ignore it.
```

The API decides "needs photos" and "needs disclosure" from these attributes through the registry, never
from the engine name (FR-016).

## Slideshow provider (`slideshow`)

| Attribute | Value |
|-----------|-------|
| requires_photos | True |
| sends_data_externally | False |
| Durations | 5–10 s (same rule as other engines) |
| Audio | None (no audio stream) |
| Enabled | Always (no GPU, no key); listed in production as well |

Behaviour: renders `source_image_path` with the requested `motion` for the full duration at the
requested size and fps. A request with `source_image_path=None` raises `ProviderError(transient=False)`
with message "This engine needs a photo for every scene."

## Contract suite changes

| Test | Change |
|------|--------|
| T2V request produces a clip | Runs only for providers with `requires_photos=False`. For `requires_photos=True`, the test asserts a permanent `ProviderError` and no file at `output_path`. |
| Motion is honoured (NEW) | For slideshow: first and last frames differ for every motion; for `zoom_in`, the centre crop of the last frame is a magnified version of the first (structural similarity check on a test pattern image). Other providers: passing a motion does not change success. |
| Unknown motion (NEW) | Permanent `ProviderError` for slideshow; ignored by other providers. |
| Attributes present (NEW) | Every registered provider exposes `requires_photos` and `sends_data_externally` as booleans. |

The slideshow provider runs the full suite in CI (no GPU).
