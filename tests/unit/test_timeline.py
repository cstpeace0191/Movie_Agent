import pytest

from server.worker.pipeline.timeline import AUTO_TRANSITIONS, build_timeline


def _starts(tl):
    return [round(s.start_seconds, 6) for s in tl.scenes]


def test_none_transition_places_scenes_back_to_back():
    tl = build_timeline([5.0, 5.0, 5.0], [None, None, None], "none", 0.5)
    assert _starts(tl) == [0.0, 5.0, 10.0]
    assert tl.total_seconds == pytest.approx(15.0)
    assert all(s.transition_seconds_in == 0.0 for s in tl.scenes)
    assert all(s.transition_in == "none" for s in tl.scenes)


def test_fade_overlaps_neighbours():
    tl = build_timeline([5.0, 5.0, 5.0], [None, None, None], "fade", 1.0)
    assert _starts(tl) == [0.0, 4.0, 8.0]
    assert tl.total_seconds == pytest.approx(13.0)
    assert tl.scenes[0].transition_in == "none"
    assert tl.scenes[0].transition_seconds_in == 0.0
    assert [s.transition_in for s in tl.scenes[1:]] == ["fade", "fade"]


def test_transition_clamped_to_half_the_shorter_neighbour():
    tl = build_timeline([5.0, 3.0], [None, None], "fade", 2.0)
    assert tl.scenes[1].transition_seconds_in == pytest.approx(1.5)
    assert tl.total_seconds == pytest.approx(6.5)


def test_single_scene_has_no_transition():
    tl = build_timeline([7.0], [None], "dissolve", 1.0)
    assert tl.total_seconds == pytest.approx(7.0)
    assert tl.scenes[0].transition_in == "none"


def test_auto_never_repeats_consecutively():
    tl = build_timeline([5.0] * 7, [None] * 7, "auto", 0.5)
    styles = [s.transition_in for s in tl.scenes[1:]]
    assert len(styles) == 6
    assert all(st in AUTO_TRANSITIONS for st in styles)
    assert all(a != b for a, b in zip(styles, styles[1:]))


def test_per_scene_override_beats_job_default():
    tl = build_timeline([5.0, 5.0, 5.0], [None, "slide_left", "none"], "fade", 1.0)
    assert [s.transition_in for s in tl.scenes] == ["none", "slide_left", "none"]
    assert _starts(tl) == [0.0, 4.0, 9.0]


def test_measured_lengths_are_used():
    tl = build_timeline([4.2, 5.0], [None, None], "none", 0.5)
    assert tl.scenes[0].length_seconds == pytest.approx(4.2)
    assert tl.scenes[1].start_seconds == pytest.approx(4.2)
    assert tl.total_seconds == pytest.approx(9.2)


def test_rejects_bad_input():
    with pytest.raises(ValueError):
        build_timeline([], [], "none", 0.5)
    with pytest.raises(ValueError):
        build_timeline([5.0, 5.0], [None], "none", 0.5)
    with pytest.raises(ValueError):
        build_timeline([5.0, 0.0], [None, None], "none", 0.5)
    with pytest.raises(ValueError):
        build_timeline([5.0, 5.0], [None, None], "spin", 0.5)
