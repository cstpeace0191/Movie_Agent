import os
import subprocess

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
from server.worker.providers.base import ProviderError, ShotRequest, ShotResult


class MockVideoProvider:
    name: str = "mock"
    requires_photos: bool = False
    sends_data_externally: bool = False

    def __init__(self):
        self.attempt_counts: dict[int, int] = {}

    def generate(self, request: ShotRequest) -> ShotResult:
        # Duration check (1-10 seconds)
        if request.duration_seconds < 1.0 or request.duration_seconds > 10.0:
            raise ProviderError("Duration must be between 1 and 10 seconds", transient=False)

        # Source image check
        if request.source_image_path is not None and not request.source_image_path.exists():
            raise ProviderError(
                f"Source image not found: {request.source_image_path}", transient=False
            )

        # Simulated timeout check
        if os.getenv("MOCK_SIMULATE_TIMEOUT") == "1":
            raise ProviderError("Simulated provider timeout", transient=True)

        # Simulated mid-generation failure
        if os.getenv("MOCK_FAIL_MIDGEN") == "1":
            raise ProviderError("Simulated mid-generation failure", transient=False)

        # MOCK_FAIL_SHOTS check (format: "position:attempt", e.g. "2:1")
        shot_pos = 0
        try:
            name_stem = request.output_path.stem
            if "_" in name_stem:
                shot_pos = int(name_stem.split("_")[-1])
        except Exception:
            pass

        current_attempt = self.attempt_counts.get(shot_pos, 0) + 1
        self.attempt_counts[shot_pos] = current_attempt

        fail_config = os.getenv("MOCK_FAIL_SHOTS")
        if fail_config:
            rules = [r.strip() for r in fail_config.split(",")]
            for rule in rules:
                if ":" in rule:
                    p_str, a_str = rule.split(":")
                    if shot_pos == int(p_str) and current_attempt == int(a_str):
                        raise ProviderError(
                            f"Injected shot {shot_pos} failure on attempt {current_attempt}",
                            transient=True,
                        )

        # Ensure output directory exists
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = request.output_path.with_suffix(".tmp.mp4")
        if temp_output.exists():
            temp_output.unlink()

        ffmpeg = get_ffmpeg_cmd()

        # If a source image is provided and exists, render the image as the video frames
        generated_from_image = False
        if request.source_image_path is not None and request.source_image_path.exists():
            vf_filter = (
                f"scale={request.width}:{request.height}:force_original_aspect_ratio=decrease,"
                f"pad={request.width}:{request.height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"setsar=1"
            )
            img_cmd = [
                ffmpeg,
                "-nostdin",
                "-y",
                "-loop",
                "1",
                "-i",
                str(request.source_image_path),
                "-t",
                str(request.duration_seconds),
                "-r",
                str(request.fps),
                "-vf",
                vf_filter,
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                str(temp_output),
            ]
            try:
                res = subprocess.run(
                    img_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
                )
                if res.returncode == 0 and temp_output.exists() and temp_output.stat().st_size > 0:
                    generated_from_image = True
            except Exception:
                if temp_output.exists():
                    temp_output.unlink()
                generated_from_image = False

        if not generated_from_image:
            # Fallback to solid color for mock (e.g. T2V or dummy test image):
            # darkgreen for I2V fallback vs navy for T2V
            color = "darkgreen" if request.source_image_path is not None else "navy"

            cmd = [
                ffmpeg,
                "-nostdin",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s={request.width}x{request.height}:d={request.duration_seconds}:r={request.fps}",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
                str(temp_output),
            ]

            try:
                res = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
                )
                if res.returncode != 0:
                    raise ProviderError(
                        f"FFmpeg generation failed: {res.stderr.decode('utf-8', errors='ignore')}",
                        transient=False,
                    )
            except subprocess.TimeoutExpired:
                if temp_output.exists():
                    temp_output.unlink()
                raise ProviderError("FFmpeg generation timed out", transient=True)
            except Exception as e:
                if temp_output.exists():
                    temp_output.unlink()
                raise ProviderError(f"Failed to generate clip: {str(e)}", transient=False)

        # Atomic move to final output path
        temp_output.replace(request.output_path)

        return ShotResult(
            clip_path=request.output_path,
            duration_seconds=float(request.duration_seconds),
            width=request.width,
            height=request.height,
            fps=request.fps,
        )
