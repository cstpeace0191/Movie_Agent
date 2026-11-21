from pathlib import Path

from server.worker.pipeline.compose import XFADE_NAMES, ClipInput, build_compose_command
from server.worker.pipeline.probe import MediaInfo
from server.worker.pipeline.timeline import build_timeline


def _clip(name: str, seconds: float, has_audio: bool = False, w: int = 832, h: int = 480):
    return ClipInput(
        path=Path(f"/clips/{name}.mp4"),
        info=MediaInfo(duration_seconds=seconds, width=w, height=h, fps=16, has_audio=has_audio),
    )


def _graph(cmd: list[str]) -> str:
    return cmd[cmd.index("-filter_complex") + 1]


def test_every_input_is_normalized():
    clips = [_clip("a", 5.0, w=640), _clip("b", 5.0)]
    tl = build_timeline([5.0, 5.0], [None, None], "none", 0.5)
    graph = _graph(build_compose_command(tl, clips, 832, 480, 16, Path("/out/final.mp4")))
    for i in range(2):
        assert (
            f"[{i}:v]scale=832:480:force_original_aspect_ratio=decrease,"
            "pad=832:480:(ow-iw)/2:(oh-ih)/2" in graph
        )
    assert graph.count("fps=16") == 2
    assert "trim=duration=5" in graph


def test_none_uses_concat_and_fade_uses_xfade_with_offsets():
    clips = [_clip("a", 5.0), _clip("b", 5.0), _clip("c", 5.0)]
    tl = build_timeline([5.0] * 3, [None, None, "none"], "fade", 1.0)
    graph = _graph(build_compose_command(tl, clips, 832, 480, 16, Path("/out/final.mp4")))
    assert "xfade=transition=fade:duration=1:offset=4" in graph
    assert graph.count("xfade=") == 1
    assert "concat=n=2:v=1:a=0" in graph


def test_spec_names_map_to_xfade_names():
    assert XFADE_NAMES == {
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
    clips = [_clip("a", 5.0), _clip("b", 5.0)]
    tl = build_timeline([5.0, 5.0], [None, "fade_black"], "none", 0.5)
    graph = _graph(build_compose_command(tl, clips, 832, 480, 16, Path("/o.mp4")))
    assert "xfade=transition=fadeblack" in graph


def test_no_audio_inputs_means_no_audio_output():
    clips = [_clip("a", 5.0), _clip("b", 5.0)]
    tl = build_timeline([5.0, 5.0], [None, None], "fade", 0.5)
    cmd = build_compose_command(tl, clips, 832, 480, 16, Path("/o.mp4"))
    assert "anullsrc" not in " ".join(cmd)
    assert "-c:a" not in cmd
    assert cmd.count("-map") == 1


def test_scene_audio_is_kept_and_silence_fills_gaps():
    clips = [_clip("a", 5.0, has_audio=True), _clip("b", 5.0, has_audio=False)]
    tl = build_timeline([5.0, 5.0], [None, None], "fade", 1.0)
    cmd = build_compose_command(tl, clips, 832, 480, 16, Path("/o.mp4"))
    joined = " ".join(cmd)
    assert "anullsrc" in joined
    assert "acrossfade=d=1" in _graph(cmd)
    assert cmd.count("-map") == 2
    assert "-c:a" in cmd


def test_single_clip():
    tl = build_timeline([5.0], [None], "fade", 1.0)
    cmd = build_compose_command(tl, [_clip("a", 5.0)], 832, 480, 16, Path("/o.mp4"))
    graph = _graph(cmd)
    assert "xfade" not in graph
    assert "concat" not in graph
    assert cmd[-1] == str(Path("/o.mp4"))


def test_compose_runs_and_normalizes_mixed_clips(tmp_path: Path):
    """FR-013: clips of different size and fps become one size and fps; fade shortens the total."""
    import subprocess

    from server.worker.pipeline.compose import compose
    from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
    from server.worker.pipeline.probe import probe_media

    def make(name: str, size: str, rate: int, audio: bool) -> Path:
        out = tmp_path / f"{name}.mp4"
        cmd = [
            get_ffmpeg_cmd(),
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=red:s={size}:d=3:r={rate}",
        ]
        if audio:
            cmd += [
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=330:duration=3",
                "-c:a",
                "aac",
                "-shortest",
            ]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return out

    paths = [make("a", "640x480", 25, True), make("b", "320x240", 16, False)]
    clips = [ClipInput(path=p, info=probe_media(p)) for p in paths]
    tl = build_timeline([c.info.duration_seconds for c in clips], [None, None], "dissolve", 1.0)
    out = compose(tl, clips, 832, 480, 16, tmp_path / "final.mp4")
    info = probe_media(out)
    assert (info.width, info.height, info.fps) == (832, 480, 16)
    assert abs(info.duration_seconds - 5.0) <= 0.15
    assert info.has_audio is True
