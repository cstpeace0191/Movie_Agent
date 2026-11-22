import subprocess
from pathlib import Path

from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
from server.worker.pipeline.probe import probe_media


def _make_clip(path: Path, with_audio: bool) -> Path:
    cmd = [
        get_ffmpeg_cmd(),
        "-nostdin",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=320x240:d=2:r=16",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    return path


def test_probe_video_without_audio(tmp_path: Path):
    clip = _make_clip(tmp_path / "v.mp4", with_audio=False)
    info = probe_media(clip)
    assert abs(info.duration_seconds - 2.0) <= 0.05
    assert info.width == 320
    assert info.height == 240
    assert info.fps == 16
    assert info.has_audio is False


def test_probe_video_with_audio(tmp_path: Path):
    clip = _make_clip(tmp_path / "va.mp4", with_audio=True)
    info = probe_media(clip)
    assert info.has_audio is True
    assert abs(info.duration_seconds - 2.0) <= 0.1


def test_probe_missing_file_raises(tmp_path: Path):
    import pytest

    with pytest.raises(FileNotFoundError):
        probe_media(tmp_path / "missing.mp4")
