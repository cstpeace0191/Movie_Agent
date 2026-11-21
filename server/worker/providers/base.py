from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ShotRequest:
    prompt: str  # scene description (required, non-empty)
    duration_seconds: float  # 5–10
    width: int
    height: int
    fps: int
    source_image_path: Path | None  # None for text-to-video (T2V)
    output_path: Path  # provider writes the clip here
    # Feature 002: zoom_in | zoom_out | pan_left | pan_right | pan_up | pan_down, resolved by the
    # worker. Providers that do not animate still images MUST ignore it.
    motion: str | None = None


@dataclass(frozen=True)
class ShotResult:
    clip_path: Path  # equals output_path on success
    duration_seconds: float  # measured from the file, not requested
    width: int
    height: int
    fps: int


class ProviderError(Exception):
    """Exception raised when a video generator provider fails to create a shot clip."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient
        self.message = message


class VideoProvider(Protocol):
    """Protocol defining the standard interface for all video generation engines.

    Class attributes (feature 002 contract delta):
        requires_photos: True if the engine cannot do text-to-video.
        sends_data_externally: True if scenario text or photos leave the server.
    """

    name: str
    requires_photos: bool
    sends_data_externally: bool

    def generate(self, request: ShotRequest) -> ShotResult:
        """Generate one clip. Blocks until done or fails. Called from a worker only."""
        ...
