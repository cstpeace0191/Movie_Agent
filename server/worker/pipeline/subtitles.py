"""Subtitle generation for SRT and ASS formats (feature 002, FR-047, FR-048).

Writes .srt and .ass subtitle files with styling based on RenderOptions.
Supports 9 caption positions:
- top_left (Alignment 7)
- top_center / top (Alignment 8)
- top_right (Alignment 9)
- middle_left (Alignment 4)
- middle_center / middle (Alignment 5)
- middle_right (Alignment 6)
- bottom_left (Alignment 1)
- bottom_center / bottom / auto (Alignment 2)
- bottom_right (Alignment 3)
"""

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from server.app.models import Scene
    from server.app.render_options import RenderOptions
    from server.worker.pipeline.timeline import Timeline


ALIGNMENT_MAP: dict[str, int] = {
    "top_left": 7,
    "top_center": 8,
    "top": 8,
    "top_right": 9,
    "middle_left": 4,
    "middle_center": 5,
    "middle": 5,
    "middle_right": 6,
    "bottom_left": 1,
    "bottom_center": 2,
    "bottom": 2,
    "auto": 2,
    "bottom_right": 3,
}

FONT_SIZE_MAP: dict[str, int] = {
    "small": 20,
    "medium": 26,
    "large": 32,
}


def _hex_to_ass_color(hex_color: str) -> str:
    """Convert '#RRGGBB' to ASS '&H00BBGGRR'."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return "&H00FFFFFF"
    r = hex_color[0:2].upper()
    g = hex_color[2:4].upper()
    b = hex_color[4:6].upper()
    return f"&H00{b}{g}{r}"


def _format_srt_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_sec = total_ms // 1000
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_ass_time(seconds: float) -> str:
    """Format seconds into H:MM:SS.cs (centiseconds)."""
    if seconds < 0:
        seconds = 0
    total_cs = int(round(seconds * 100))
    cs = total_cs % 100
    total_sec = total_cs // 100
    s = total_sec % 60
    total_min = total_sec // 60
    m = total_min % 60
    h = total_min // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def write_srt(
    timeline: "Timeline | None",
    scenes: Sequence[Any],
    output_path: Path,
) -> Path:
    """Write an SRT subtitle file from scenes.

    Each cue spans [scene.start_seconds, scene.start_seconds + scene.length_seconds].
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cues: list[str] = []
    cue_idx = 1
    for sc in scenes:
        text = (getattr(sc, "caption", None) or "").strip()
        if not text:
            continue
        start_sec = float(getattr(sc, "start_seconds", 0.0) or 0.0)
        dur_sec = float(getattr(sc, "length_seconds", 0.0) or getattr(sc, "duration_seconds", 5.0) or 5.0)
        end_sec = start_sec + dur_sec
        start_str = _format_srt_time(start_sec)
        end_str = _format_srt_time(end_sec)
        cues.append(f"{cue_idx}\n{start_str} --> {end_str}\n{text}\n")
        cue_idx += 1

    content = "\n".join(cues)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_ass(
    timeline: "Timeline | None",
    scenes: Sequence[Any],
    options: "RenderOptions",
    width: int,
    height: int,
    output_path: Path,
) -> Path:
    """Write an ASS subtitle file from scenes with styling according to options.

    Supports 9 caption positions via ASS alignment.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    position = getattr(options, "caption_position", "bottom_center") or "bottom_center"
    alignment = ALIGNMENT_MAP.get(position, 2)
    font_size = FONT_SIZE_MAP.get(getattr(options, "caption_size", "medium"), 26)
    primary_color = _hex_to_ass_color(getattr(options, "caption_color", "#FFFFFF") or "#FFFFFF")
    border_style = 3 if getattr(options, "caption_box", True) else 1
    # 60% black box: &H66000000 (alpha=102/255 -> ~0x66)
    back_color = "&H66000000" if border_style == 3 else "&H80000000"

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,NanumGothic,{font_size},{primary_color},&H000000FF,&H00000000,{back_color},1,0,0,0,100,100,0,0,{border_style},3,1,{alignment},30,30,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    dialogues: list[str] = []
    for sc in scenes:
        text = (getattr(sc, "caption", None) or "").strip()
        if not text:
            continue
        start_sec = float(getattr(sc, "start_seconds", 0.0) or 0.0)
        dur_sec = float(getattr(sc, "length_seconds", 0.0) or getattr(sc, "duration_seconds", 5.0) or 5.0)
        end_sec = start_sec + dur_sec
        start_str = _format_ass_time(start_sec)
        end_str = _format_ass_time(end_sec)
        # Escape for ASS
        escaped_text = text.replace("\\", "").replace("\n", "\\N").replace("\r", "")
        dialogues.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{escaped_text}")

    full_content = header + "\n".join(dialogues) + "\n"
    output_path.write_text(full_content, encoding="utf-8")
    return output_path

