from pathlib import Path

from server.worker.pipeline.frames import extract_last_frame
from server.worker.providers.base import ShotRequest
from server.worker.providers.mock import MockVideoProvider


def test_extract_last_frame(tmp_path: Path):
    clip_path = tmp_path / "test_clip.mp4"
    frame_path = tmp_path / "last_frame.png"

    provider = MockVideoProvider()
    req = ShotRequest(
        prompt="Test clip",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=clip_path,
    )
    res = provider.generate(req)
    assert res.clip_path.exists()

    result_frame = extract_last_frame(clip_path, frame_path, width=832, height=480)
    assert result_frame.exists()
    assert result_frame == frame_path
    assert result_frame.stat().st_size > 0
