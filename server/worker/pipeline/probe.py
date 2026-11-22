"""Media probing with the FFmpeg binary (no ffprobe needed, works with imageio-ffmpeg)."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #\S+.*?Video:.*?(\d{2,5})x(\d{2,5})")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps")
_AUDIO_RE = re.compile(r"Stream #\S+.*?Audio:")
_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class MediaInfo:
    """Measured properties of a media file."""

    duration_seconds: float
    width: int
    height: int
    fps: int
    has_audio: bool


def probe_media(path: Path) -> MediaInfo:
    """Measure duration, frame size, frame rate, and audio presence of ``path``.

    The duration is decoded (``-f null``), not read from the container header, so it matches what
    a filter graph will actually see.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        RuntimeError: if FFmpeg cannot read the file.
    """
    if not path.exists():
        raise FileNotFoundError(f"Media not found: {path}")

    proc = subprocess.run(
        [get_ffmpeg_cmd(), "-hide_banner", "-nostdin", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    err = proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(f"Cannot read media {path}: {err[-500:]}")

    video = _VIDEO_RE.search(err)
    if not video:
        raise RuntimeError(f"No video stream in {path}")
    stream_line = err[video.start() : err.find("\n", video.start())]
    fps_match = _FPS_RE.search(stream_line)

    return MediaInfo(
        duration_seconds=_decoded_duration(err),
        width=int(video.group(1)),
        height=int(video.group(2)),
        fps=round(float(fps_match.group(1))) if fps_match else 0,
        has_audio=bool(_AUDIO_RE.search(err)),
    )


def _decoded_duration(stderr: str) -> float:
    times = _TIME_RE.findall(stderr)
    if times:
        h, m, s = times[-1]
        return int(h) * 3600 + int(m) * 60 + float(s)
    header = _DURATION_RE.search(stderr)
    if header:
        h, m, s = header.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError("Could not determine media duration")
