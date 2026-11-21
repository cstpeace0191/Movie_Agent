import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from server.app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def gen_uuid() -> str:
    return str(uuid.uuid4())


# Validation helpers
USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_username(username: str) -> bool:
    if not isinstance(username, str):
        return False
    return bool(USERNAME_REGEX.match(username))


def validate_email(email: str | None) -> bool:
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_password(password: str) -> bool:
    if not isinstance(password, str):
        return False
    return len(password) >= 12


def validate_alt_text(alt: str | None) -> bool:
    if alt is None or alt == "":
        return True
    return len(alt) <= 500


def validate_job_progress(progress: int) -> bool:
    return 0 <= progress <= 100


def validate_scene_positions(positions: list[int]) -> bool:
    if not positions:
        return True
    return positions == list(range(len(positions)))


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(32), unique=True, index=True, nullable=False)
    username_lower = Column(String(32), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    country = Column(String(64), nullable=True)
    phone = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String(64), nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="owner", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    token_hash = Column(String(64), primary_key=True, index=True)
    user_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_token = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)

    user = relationship("User", back_populates="sessions")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    owner_id = Column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    input_mode = Column(String(32), nullable=False)  # TEXT_ONLY, IMAGE_ONLY, TEXT_IMAGE
    scenario = Column(Text, nullable=True)
    status = Column(
        String(32), default="queued", nullable=False, index=True
    )  # drafting, awaiting_review, queued, running, succeeded, failed, expired
    progress = Column(Integer, default=0, nullable=False)
    message = Column(String(200), default="Queued", nullable=False)
    failure_reason = Column(String(500), nullable=True)

    width = Column(Integer, default=832, nullable=False)
    height = Column(Integer, default=480, nullable=False)
    seconds_per_shot = Column(Float, default=5.0, nullable=False)
    fps = Column(Integer, default=16, nullable=False)
    chain_frames = Column(Boolean, default=True, nullable=False)
    provider = Column(String(64), default="mock", nullable=False)
    external_consent_at = Column(DateTime, nullable=True)

    planned_seconds = Column(Float, default=0.0, nullable=False)
    unused_image_count = Column(Integer, default=0, nullable=False)
    final_video_path = Column(String(500), nullable=True)

    # Feature 002 (data-model.md). Render options default to {} = feature 001 behaviour.
    render_options = Column(JSON, default=dict, nullable=True)
    text_assist_consent_at = Column(DateTime, nullable=True)
    review_confirmed_at = Column(DateTime, nullable=True)
    bgm_path = Column(String(500), nullable=True)
    subtitles_srt_path = Column(String(500), nullable=True)
    subtitles_ass_path = Column(String(500), nullable=True)
    final_duration_seconds = Column(Float, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    owner = relationship("User", back_populates="jobs")
    scenes = relationship(
        "Scene", back_populates="job", cascade="all, delete-orphan", order_by="Scene.position"
    )
    shots = relationship(
        "Shot", back_populates="job", cascade="all, delete-orphan", order_by="Shot.position"
    )
    source_images = relationship(
        "SourceImage",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="SourceImage.position",
    )


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    duration_seconds = Column(Float, default=5.0, nullable=False)
    source_image_id = Column(
        String(36), ForeignKey("source_images.id", ondelete="SET NULL"), nullable=True
    )
    split_method = Column(String(32), default="paragraph", nullable=False)

    # Feature 002 (data-model.md). Card scenes (kind title/ending) may have empty description.
    kind = Column(String(16), default="scene", nullable=False)  # scene, title, ending
    caption = Column(Text, nullable=True)
    caption_source = Column(String(16), nullable=True)  # assisted, verbatim, user
    narration = Column(Text, nullable=True)
    transition = Column(String(32), nullable=True)  # null = job default; transition INTO scene
    motion = Column(String(16), nullable=True)
    start_seconds = Column(Float, nullable=True)  # timeline result
    length_seconds = Column(Float, nullable=True)  # measured clip length on the timeline

    job = relationship("Job", back_populates="scenes")
    source_image = relationship("SourceImage")

    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_scene_job_position"),)


class Shot(Base):
    __tablename__ = "shots"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=False)
    status = Column(
        String(32), default="pending", nullable=False
    )  # pending, generating, succeeded, failed
    attempts = Column(Integer, default=0, nullable=False)
    clip_path = Column(String(500), nullable=True)
    error_message = Column(String(1000), nullable=True)

    job = relationship("Job", back_populates="shots")
    scene = relationship("Scene")

    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_shot_job_position"),)


class SourceImage(Base):
    __tablename__ = "source_images"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_id = Column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    media_type = Column(String(64), nullable=False)  # image/jpeg, image/png, image/webp
    size_bytes = Column(Integer, nullable=False)
    alt_text = Column(String(500), nullable=True)
    storage_path = Column(String(500), nullable=False)
    used = Column(Boolean, default=True, nullable=False)
    note = Column(String(500), nullable=True)  # feature 002: note for caption, <= 500 chars

    job = relationship("Job", back_populates="source_images")

    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_image_job_position"),)


class SentEmail(Base):
    __tablename__ = "sent_emails"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    recipient = Column(String(255), index=True, nullable=False)
    sender = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    body_text = Column(Text, nullable=False)
    verification_code = Column(String(16), nullable=True)
    status = Column(String(32), default="delivered", nullable=False)
    created_at = Column(DateTime, default=utcnow, index=True, nullable=False)
