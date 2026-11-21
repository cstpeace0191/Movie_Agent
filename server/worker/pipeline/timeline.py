"""Scene timeline (feature 002, FR-041/FR-042, research R1).

Pure functions only: no I/O. Every later step (compose, subtitles, music) uses these times, so time
is computed in exactly one place.

Rules (specify.txt section 6.1):
    t_i = min(T, d_{i-1} / 2, d_i / 2)   transition into scene i; 0 for scene 0 and for "none"
    s_0 = 0,  s_i = s_{i-1} + d_{i-1} - t_i
    total = s_last + d_last  (= sum(d) - sum(t))
"""

from collections.abc import Sequence
from dataclasses import dataclass

from server.app.render_options import TRANSITIONS

# Fixed cycle for "auto": consecutive entries differ, so neighbouring scene changes differ.
AUTO_TRANSITIONS: tuple[str, ...] = (
    "fade",
    "slide_left",
    "dissolve",
    "wipe_left",
    "circle_open",
    "slide_up",
)


@dataclass(frozen=True)
class TimelineScene:
    """One scene's place on the output timeline."""

    position: int
    start_seconds: float
    length_seconds: float
    transition_in: str  # concrete style ("none" for the first scene and for cuts)
    transition_seconds_in: float  # overlap with the previous scene

    @property
    def end_seconds(self) -> float:
        return self.start_seconds + self.length_seconds


@dataclass(frozen=True)
class Timeline:
    """All scenes in order, with their start times and the transitions between them."""

    scenes: tuple[TimelineScene, ...]

    @property
    def total_seconds(self) -> float:
        last = self.scenes[-1]
        return last.start_seconds + last.length_seconds


def build_timeline(
    lengths: Sequence[float],
    transitions: Sequence[str | None],
    default_transition: str,
    transition_seconds: float,
) -> Timeline:
    """Place scenes on one timeline.

    Args:
        lengths: Measured length of each scene's clip, in seconds (all > 0).
        transitions: Per-scene transition *into* that scene; ``None`` means the job default.
            Entry 0 is ignored (the first scene never has a transition).
        default_transition: The job's transition style (a RenderOptions value).
        transition_seconds: Requested transition length before clamping.

    Returns:
        The computed Timeline.

    Raises:
        ValueError: on empty input, mismatched lengths, non-positive lengths, or unknown style.
    """
    if not lengths:
        raise ValueError("A timeline needs at least one scene")
    if len(lengths) != len(transitions):
        raise ValueError("lengths and transitions must have the same number of entries")
    if any(d <= 0 for d in lengths):
        raise ValueError("Every scene length must be positive")
    for style in (default_transition, *transitions):
        if style is not None and style not in TRANSITIONS:
            raise ValueError(f"Unknown transition: {style}")

    scenes: list[TimelineScene] = []
    start = 0.0
    for i, length in enumerate(lengths):
        if i == 0:
            style, overlap = "none", 0.0
        else:
            style = _resolve_style(transitions[i] or default_transition, change_index=i - 1)
            overlap = 0.0
            if style != "none":
                overlap = min(transition_seconds, lengths[i - 1] / 2, length / 2)
            start = scenes[-1].end_seconds - overlap
        scenes.append(
            TimelineScene(
                position=i,
                start_seconds=start,
                length_seconds=float(length),
                transition_in=style,
                transition_seconds_in=overlap,
            )
        )
    return Timeline(scenes=tuple(scenes))


def _resolve_style(style: str, change_index: int) -> str:
    if style == "auto":
        return AUTO_TRANSITIONS[change_index % len(AUTO_TRANSITIONS)]
    return style
