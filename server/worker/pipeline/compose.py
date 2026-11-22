"""Join scene clips on a Timeline into the final MP4 (feature 002, FR-041/FR-042/FR-013).

One FFmpeg filter graph normalizes every clip to the job's size and frame rate, then joins
neighbours with ``xfade`` (when the timeline has an overlap) or ``concat`` (straight cut). Scene
audio is kept: clips without audio get a silent track so every input has audio, and audio joins use
``acrossfade`` where video uses ``xfade``. With no audio anywhere, no audio stream is written.

Replaces feature 001's ``join.py`` (research R2).
"""

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
from server.worker.pipeline.probe import MediaInfo
from server.worker.pipeline.timeline import Timeline

# Spec transition identifiers -> FFmpeg xfade transition names (research R3).
XFADE_NAMES: dict[str, str] = {
    "fade": "fade",
    "fade_black": "fadeblack",
    "fade_white": "fadewhite",
    "dissolve": "dissolve",
    "slide_left": "slideleft",
    "slide_right": "slideright",
    "slide_up": "slideup",
    "slide_down": "slidedown",
    "wipe_left": "wipeleft",
    "circle_open": "circleopen",
    "zoom_in": "zoomin",
}

COMPOSE_TIMEOUT_SECONDS = 900
AUDIO_RATE = 48000


@dataclass(frozen=True)
class ClipInput:
    """A scene clip and its measured properties."""

    path: Path
    info: MediaInfo


def _num(value: float) -> str:
    """Format seconds for FFmpeg without float noise (5.0 -> '5', 4.25 -> '4.25')."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def build_compose_command(
    timeline: Timeline,
    clips: Sequence[ClipInput],
    width: int,
    height: int,
    fps: int,
    output_path: Path,
    subtitles_path: Path | None = None,
) -> list[str]:
    """Build the FFmpeg command that renders ``timeline`` from ``clips`` to ``output_path``.

    Raises:
        ValueError: if the number of clips differs from the number of timeline scenes.
    """
    if len(clips) != len(timeline.scenes):
        raise ValueError("Each timeline scene needs exactly one clip")

    args: list[str] = [get_ffmpeg_cmd(), "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for clip in clips:
        args += ["-i", str(clip.path)]

    with_audio = any(c.info.has_audio for c in clips)
    silent_input: dict[int, int] = {}
    if with_audio:
        next_index = len(clips)
        for i, clip in enumerate(clips):
            if not clip.info.has_audio:
                length = _num(timeline.scenes[i].length_seconds)
                args += [
                    "-f",
                    "lavfi",
                    "-t",
                    length,
                    "-i",
                    f"anullsrc=r={AUDIO_RATE}:cl=stereo",
                ]
                silent_input[i] = next_index
                next_index += 1

    parts: list[str] = []
    for i, scene in enumerate(timeline.scenes):
        d = _num(scene.length_seconds)
        parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p,"
            f"trim=duration={d},setpts=PTS-STARTPTS,settb=AVTB,fps={fps}[v{i}]"
        )
        if with_audio:
            src = silent_input.get(i, i)
            parts.append(
                f"[{src}:a]aresample={AUDIO_RATE},aformat=channel_layouts=stereo,"
                f"atrim=duration={d},asetpts=PTS-STARTPTS[a{i}]"
            )

    video_out, audio_out = "v0", "a0"
    for i, scene in enumerate(timeline.scenes[1:], start=1):
        t = scene.transition_seconds_in
        if t > 0:
            name = XFADE_NAMES[scene.transition_in]
            parts.append(
                f"[{video_out}][v{i}]xfade=transition={name}:duration={_num(t)}"
                f":offset={_num(scene.start_seconds)}[vx{i}]"
            )
            if with_audio:
                parts.append(f"[{audio_out}][a{i}]acrossfade=d={_num(t)}[ax{i}]")
        else:
            parts.append(f"[{video_out}][v{i}]concat=n=2:v=1:a=0[vx{i}]")
            if with_audio:
                parts.append(f"[{audio_out}][a{i}]concat=n=2:v=0:a=1[ax{i}]")
        video_out, audio_out = f"vx{i}", f"ax{i}"

    if subtitles_path and Path(subtitles_path).exists():
        sub_str = Path(subtitles_path).resolve().as_posix().replace(":", r"\:")
        fonts_dir = (Path(__file__).resolve().parent.parent.parent / "assets" / "fonts").resolve().as_posix().replace(":", r"\:")
        parts.append(f"[{video_out}]subtitles={sub_str}:fontsdir={fonts_dir}[vsub]")
        video_out = "vsub"

    args += ["-filter_complex", ";".join(parts), "-map", f"[{video_out}]"]
    if with_audio:
        args += ["-map", f"[{audio_out}]", "-c:a", "aac", "-b:a", "160k"]
    args += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    return args


def compose(
    timeline: Timeline,
    clips: Sequence[ClipInput],
    width: int,
    height: int,
    fps: int,
    output_path: Path,
    subtitles_path: Path | None = None,
) -> Path:
    """Render the final video and atomically replace ``output_path``.

    Raises:
        RuntimeError: if FFmpeg fails; the message ends with FFmpeg's last error lines.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output_path.with_suffix(".tmp.mp4")
    if temp_output.exists():
        temp_output.unlink()

    cmd = build_compose_command(
        timeline, clips, width, height, fps, temp_output, subtitles_path=subtitles_path
    )
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=COMPOSE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        if temp_output.exists():
            temp_output.unlink()
        raise RuntimeError("Joining scenes timed out") from exc
    if proc.returncode != 0 or not temp_output.exists():
        if temp_output.exists():
            temp_output.unlink()
        raise RuntimeError(f"Joining scenes failed: {proc.stderr.strip()[-500:]}")

    temp_output.replace(output_path)
    return output_path
