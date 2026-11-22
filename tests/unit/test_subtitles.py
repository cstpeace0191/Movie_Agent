from dataclasses import dataclass
from pathlib import Path
import pytest

from server.app.render_options import parse_render_options
from server.worker.pipeline.subtitles import (
    ALIGNMENT_MAP,
    write_ass,
    write_srt,
    _format_srt_time,
    _format_ass_time,
)


@dataclass
class DummyScene:
    caption: str | None
    start_seconds: float
    length_seconds: float
    duration_seconds: float = 5.0


def test_srt_time_formatting():
    assert _format_srt_time(0.0) == "00:00:00,000"
    assert _format_srt_time(1.5) == "00:00:01,500"
    assert _format_srt_time(65.25) == "00:01:05,250"


def test_ass_time_formatting():
    assert _format_ass_time(0.0) == "0:00:00.00"
    assert _format_ass_time(1.5) == "0:00:01.50"
    assert _format_ass_time(65.25) == "0:01:05.25"


def test_write_srt(tmp_path: Path):
    scenes = [
        DummyScene(caption="첫 번째 사진 설명", start_seconds=0.0, length_seconds=3.0),
        DummyScene(caption="", start_seconds=3.0, length_seconds=2.0),
        DummyScene(caption="두 번째 사진 설명", start_seconds=5.0, length_seconds=4.0),
    ]
    out = tmp_path / "subtitles.srt"
    write_srt(None, scenes, out)
    content = out.read_text(encoding="utf-8")

    assert "1\n00:00:00,000 --> 00:00:03,000\n첫 번째 사진 설명" in content
    assert "2\n00:00:05,000 --> 00:00:09,000\n두 번째 사진 설명" in content


@pytest.mark.parametrize(
    "position,expected_alignment",
    [
        ("top_left", 7),
        ("top_center", 8),
        ("top", 8),
        ("top_right", 9),
        ("middle_left", 4),
        ("middle_center", 5),
        ("middle_right", 6),
        ("bottom_left", 1),
        ("bottom_center", 2),
        ("bottom", 2),
        ("auto", 2),
        ("bottom_right", 3),
    ],
)
def test_write_ass_alignments(tmp_path: Path, position: str, expected_alignment: int):
    scenes = [
        DummyScene(caption="테스트 캡션", start_seconds=0.0, length_seconds=3.0),
    ]
    opts = parse_render_options({"caption_position": position, "caption_color": "#FFFF00"})
    out = tmp_path / f"subtitles_{position}.ass"
    write_ass(None, scenes, opts, 832, 480, out)
    content = out.read_text(encoding="utf-8")

    # Check Alignment in Style line
    # Format: ..., Alignment, MarginL, MarginR, MarginV, Encoding
    # Style: Default,NanumGothic,26,&H0000FFFF,&H000000FF,&H00000000,&H66000000,1,0,0,0,100,100,0,0,3,3,1,<alignment>,30,30,30,1
    assert f",3,1,{expected_alignment},30,30,30,1" in content
    assert "Dialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,0,,테스트 캡션" in content

