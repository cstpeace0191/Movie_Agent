"""Render options for feature 002 (data-model.md, RenderOptions).

Render options change how the finished video looks (transitions, captions, music) without changing
what each scene shows. They are stored as one JSON value on ``Job.render_options``. An empty value
means every default, which reproduces the feature 001 result.
"""

from collections.abc import Mapping
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

Transition = Literal[
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
Motion = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down", "auto"]
CaptionTone = Literal["informative", "emotional", "humorous", "travel_diary", "advertisement"]
CaptionPosition = Literal[
    "top_left",
    "top_center",
    "top_right",
    "middle_left",
    "middle_center",
    "middle_right",
    "bottom_left",
    "bottom_center",
    "bottom_right",
    "top",
    "bottom",
    "auto",
    "none",
]
CaptionSize = Literal["small", "medium", "large"]

TRANSITIONS: tuple[str, ...] = get_args(Transition)


class RenderOptionsError(ValueError):
    """Raised when a render option is invalid. Maps to ``422 invalid_render_option``."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


class RenderOptions(BaseModel):
    """Validated render options with the defaults from data-model.md."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    transition: Transition = "none"
    transition_seconds: float = Field(0.5, ge=0.1, le=2.0)
    motion: Motion = "auto"
    captions: bool = False
    caption_tone: CaptionTone = "informative"
    burn_captions: bool = False
    caption_position: CaptionPosition = "bottom"
    caption_size: CaptionSize = "medium"
    caption_color: str = Field("#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    caption_box: bool = True
    title: str | None = Field(None, max_length=80)
    ending_text: str | None = Field(None, max_length=120)
    video_filename: str | None = Field(None, max_length=120)
    bgm_id: str | None = None
    bgm_volume: float = Field(0.3, ge=0.0, le=1.0)

    @field_validator("title", "ending_text", "bgm_id", "video_filename", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    def to_storage(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for ``Job.render_options``."""
        return self.model_dump()

    @classmethod
    def from_storage(cls, value: Mapping[str, Any] | None) -> "RenderOptions":
        """Rebuild options from a stored value; missing keys take their defaults."""
        return cls.model_validate(dict(value or {}))


def parse_render_options(fields: Mapping[str, Any]) -> RenderOptions:
    """Validate submitted fields. ``None`` values are treated as "not submitted".

    Raises:
        RenderOptionsError: naming the first invalid field and what is allowed.
    """
    submitted = {k: v for k, v in fields.items() if v is not None}
    try:
        return RenderOptions.model_validate(submitted)
    except ValidationError as exc:
        error = exc.errors()[0]
        field = str(error["loc"][0]) if error.get("loc") else "render_options"
        allowed = _allowed_values(field)
        detail = f"Invalid value for '{field}': {error['msg']}."
        if allowed:
            detail += f" Allowed values: {allowed}."
        raise RenderOptionsError(field, detail) from exc


def _allowed_values(field: str) -> str:
    info = RenderOptions.model_fields.get(field)
    if info is None or info.annotation is None:
        return ""
    choices = get_args(info.annotation)
    if choices and all(isinstance(c, str) for c in choices):
        return ", ".join(choices)
    return ""
