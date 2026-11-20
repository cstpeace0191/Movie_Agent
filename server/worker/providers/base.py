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
    """Protocol defining the standard interface for all video generation engines."""

    name: str

    def generate(self, request: ShotRequest) -> ShotResult:
        """Generate one clip. Blocks until done or fails. Called from a worker only."""
        ...
