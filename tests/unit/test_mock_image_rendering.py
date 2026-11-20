import subprocess
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
from server.worker.providers.base import ShotRequest
from server.worker.providers.mock import MockVideoProvider


def test_mock_provider_renders_actual_image(tmp_path: Path):
    provider = MockVideoProvider()
    ffmpeg = get_ffmpeg_cmd()

    # 1. Create a real sample image (red 120x120 PNG)
    sample_img = tmp_path / "real_photo.png"
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=120x120",
            "-frames:v",
            "1",
            str(sample_img),
        ],
        check=True,
        capture_output=True,
    )

    # 2. Request video generation using MockVideoProvider
    out_video = tmp_path / "rendered_from_photo.mp4"
    req = ShotRequest(
        prompt="Photo scene",
        duration_seconds=2.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=sample_img,
        output_path=out_video,
    )
    result = provider.generate(req)

    assert result.clip_path.exists()
    assert result.clip_path.stat().st_size > 0
    assert result.duration_seconds == 2.0
    assert result.width == 832
    assert result.height == 480
