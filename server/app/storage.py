import shutil
from pathlib import Path

from server.app.config import settings


class StorageValidationError(Exception):
    """Exception raised when an uploaded file fails size or media-type validation."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def get_storage_dir() -> Path:
    """Return the base storage directory, creating it if it does not exist."""
    storage_path = Path(settings.STORAGE_DIR)
    storage_path.mkdir(parents=True, exist_ok=True)
    return storage_path


def get_job_dir(job_id: str) -> Path:
    """Return the dedicated storage directory for a specific job."""
    job_dir = get_storage_dir() / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_image_path(job_id: str, image_id: str, extension: str) -> Path:
    """Return the path for storing an uploaded source image for a job."""
    images_dir = get_job_dir(job_id) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    ext = extension.lstrip(".")
    return images_dir / f"{image_id}.{ext}"


def get_shot_path(job_id: str, shot_position: int) -> Path:
    """Return the path for an intermediate generated shot video clip."""
    shots_dir = get_job_dir(job_id) / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    return shots_dir / f"shot_{shot_position}.mp4"


def get_final_video_path(job_id: str) -> Path:
    """Return the path for the concatenated final MP4 video."""
    return get_job_dir(job_id) / "final.mp4"


def get_subtitles_path(job_id: str, fmt: str) -> Path:
    """Return the subtitle file path for a job (``fmt`` is ``srt`` or ``ass``)."""
    if fmt not in ("srt", "ass"):
        raise ValueError(f"Unsupported subtitle format: {fmt}")
    return get_job_dir(job_id) / f"subtitles.{fmt}"


def get_bgm_path(job_id: str, extension: str) -> Path:
    """Return the path for a job's uploaded background music."""
    audio_dir = get_job_dir(job_id) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir / f"bgm.{extension.lstrip('.')}"


def get_card_path(job_id: str, kind: str) -> Path:
    """Return the clip path for a title or ending card."""
    cards_dir = get_job_dir(job_id) / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    return cards_dir / f"{kind}.mp4"


def delete_job_media(job_id: str) -> bool:
    """Remove all stored media files and directories associated with a job."""
    job_dir = get_storage_dir() / "jobs" / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
        return True
    return False


def detect_image_type(data: bytes) -> str | None:
    """Inspect magic bytes to determine image MIME type (JPEG, PNG, WebP)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_upload_file(data: bytes, original_filename: str) -> tuple[str, str]:
    """Validate uploaded image file bytes and size, returning (media_type, extension)."""
    if len(data) > settings.MAX_IMAGE_SIZE_BYTES:
        raise StorageValidationError(
            code="file_too_large",
            message=f"File '{original_filename}' exceeds 20 MB size limit.",
        )
    media_type = detect_image_type(data)
    if not media_type:
        raise StorageValidationError(
            code="unsupported_file_type",
            message=f"File '{original_filename}' is not a supported format (JPG, PNG, WebP only).",
        )
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    return media_type, ext_map[media_type]
