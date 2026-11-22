from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UserRegister(BaseModel):
    username: str
    password: str
    country: str | None = None
    phone: str | None = None
    email: str | None = None


class CheckUsernameResponse(BaseModel):
    available: bool
    message: str


class VerifyEmailRequest(BaseModel):
    username: str
    code: str


class VerifyEmailResponse(BaseModel):
    success: bool
    message_ko: str = "인증되었습니다"
    message_en: str = "You are Verified"


class ResendCodeRequest(BaseModel):
    username: str


class ResendCodeResponse(BaseModel):
    success: bool
    message: str
    email: str | None = None
    code: str | None = None


class MailMessageOut(BaseModel):
    id: str
    recipient: str
    sender: str
    subject: str
    body_text: str
    verification_code: str | None = None
    created_at: datetime


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: str
    username: str
    email: str | None = None
    country: str | None = None
    phone: str | None = None
    email_verified: bool = True
    verification_required: bool = False
    debug_code: str | None = None


class LoginResponse(BaseModel):
    id: str
    username: str
    csrf_token: str


class ProviderOut(BaseModel):
    id: str
    label: str
    location: Literal["local", "cloud"]
    enabled: bool
    is_default: bool
    sends_data_externally: bool
    requires_photos: bool = False
    max_clip_seconds: float | None = None
    disabled_reason: str | None = None


class ShotOut(BaseModel):
    id: str
    position: int
    status: str
    attempts: int
    scene_excerpt: str | None = None
    source_image_id: str | None = None
    error: str | None = None


class JobSummary(BaseModel):
    id: str
    status: str
    input_mode: str
    progress: int
    message: str
    planned_seconds: float
    created_at: datetime
    expires_at: datetime
    render_options: dict = {}


class SceneOut(BaseModel):
    """One scene on the job timeline (feature 002 contract delta)."""

    position: int
    kind: str = "scene"
    source_image_id: str | None = None
    image_url: str | None = None
    note: str | None = None
    alt_text: str | None = None
    excerpt: str | None = None
    caption: str | None = None
    caption_source: str | None = None
    transition: str | None = None
    start_seconds: float | None = None
    length_seconds: float | None = None


class SubtitleLinks(BaseModel):
    srt_url: str | None = None
    ass_url: str | None = None


class MusicCredit(BaseModel):
    title: str
    license_name: str | None = None
    license_url: str | None = None
    attribution: str | None = None


class JobOut(BaseModel):
    id: str
    status: str
    input_mode: str
    progress: int
    message: str
    failure_reason: str | None = None
    planned_seconds: float
    unused_image_count: int = 0
    created_at: datetime
    expires_at: datetime
    shots: list[ShotOut] | None = None
    # Feature 002
    render_options: dict = {}
    scenes: list[SceneOut] | None = None
    text_assist_consented: bool = False
    subtitles: SubtitleLinks | None = None
    music: MusicCredit | None = None
    final_duration_seconds: float | None = None
