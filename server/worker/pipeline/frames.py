import subprocess
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd


def extract_last_frame(
    clip_path: Path,
    output_image_path: Path,
    width: int = 832,
    height: int = 480,
) -> Path:
    """Extract the last frame from a video clip as an image using FFmpeg."""
    if not clip_path.exists():
        raise FileNotFoundError(f"Clip not found: {clip_path}")

    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_cmd()

    # Extract last frame using FFmpeg sseof
    cmd = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-sseof",
        "-0.1",
        "-i",
        str(clip_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={width}:{height}",
        str(output_image_path),
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    if res.returncode != 0:
        # Fallback to seek 0 if sseof fails
        fallback_cmd = [
            ffmpeg,
            "-nostdin",
            "-y",
            "-i",
            str(clip_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:{height}",
            str(output_image_path),
        ]
        subprocess.run(
            fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True
        )

    return output_image_path
