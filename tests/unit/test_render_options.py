import pytest

from server.app.render_options import (
    RenderOptions,
    RenderOptionsError,
    parse_render_options,
)


def test_defaults_match_data_model():
    opts = parse_render_options({})
    assert opts == RenderOptions()
    assert opts.transition == "none"
    assert opts.transition_seconds == 0.5
    assert opts.motion == "auto"
    assert opts.captions is False
    assert opts.caption_tone == "informative"
    assert opts.burn_captions is False
    assert opts.caption_position == "bottom"
    assert opts.caption_size == "medium"
    assert opts.caption_color == "#FFFFFF"
    assert opts.caption_box is True
    assert opts.title is None
    assert opts.ending_text is None
    assert opts.bgm_id is None
    assert opts.bgm_volume == 0.3


def test_none_values_are_ignored():
    opts = parse_render_options({"transition": None, "transition_seconds": None})
    assert opts.transition == "none"
    assert opts.transition_seconds == 0.5


def test_valid_values_are_kept():
    opts = parse_render_options(
        {
            "transition": "fade",
            "transition_seconds": 1.0,
            "caption_color": "#00ff00",
            "title": "  Trip  ",
            "ending_text": "",
        }
    )
    assert opts.transition == "fade"
    assert opts.transition_seconds == 1.0
    assert opts.caption_color == "#00ff00"
    assert opts.title == "Trip"
    assert opts.ending_text is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("transition_seconds", 0.05),
        ("transition_seconds", 2.5),
        ("bgm_volume", -0.1),
        ("bgm_volume", 1.1),
        ("caption_color", "white"),
        ("caption_color", "#FFF"),
        ("title", "t" * 81),
        ("ending_text", "e" * 121),
        ("transition", "spin"),
        ("motion", "orbit"),
        ("caption_tone", "angry"),
        ("caption_position", "middle"),
        ("caption_size", "huge"),
    ],
)
def test_invalid_values_raise_with_field_name(field, value):
    with pytest.raises(RenderOptionsError) as exc:
        parse_render_options({field: value})
    assert exc.value.field == field
    assert field in exc.value.message


def test_all_transition_names_accepted():
    names = [
        "none",
        "fade",
        "fade_black",
        "fade_white",
        "dissolve",
        "slide_left",
        "slide_right",
        "slide_up",
        "slide_down",
        "wipe_left",
        "circle_open",
        "zoom_in",
        "auto",
    ]
    for name in names:
        assert parse_render_options({"transition": name}).transition == name


def test_to_storage_round_trip():
    opts = parse_render_options({"transition": "dissolve", "transition_seconds": 0.8})
    stored = opts.to_storage()
    assert isinstance(stored, dict)
    assert RenderOptions.from_storage(stored) == opts
    assert RenderOptions.from_storage(None) == RenderOptions()
    assert RenderOptions.from_storage({}) == RenderOptions()
