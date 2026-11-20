import subprocess
import tempfile
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd


def join_shots(
    shot_paths: list[Path],
    output_path: Path,
    width: int = 832,
    height: int = 480,
    fps: int = 16,
) -> Path:
    """Concatenate individual shot video files into a final MP4."""
    if not shot_paths:
        raise ValueError("No shot paths provided to join")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_cmd()

    # Create temporary concat list file
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_file_path = Path(f.name)
        for shot_path in shot_paths:
            safe_path = str(shot_path.resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    temp_output = output_path.with_suffix(".tmp.mp4")
    if temp_output.exists():
        temp_output.unlink()

    cmd = [
        ffmpeg,
        "-nostdin",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file_path),
        "-c",
        "copy",
        str(temp_output),
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=True)
    except Exception:
        # Fallback to re-encode if stream copy fails
        fallback_cmd = [
            ffmpeg,
            "-nostdin",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file_path),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            str(temp_output),
        ]
        subprocess.run(
            fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=True
        )
    finally:
        if list_file_path.exists():
            list_file_path.unlink()

    temp_output.replace(output_path)
    return output_path
