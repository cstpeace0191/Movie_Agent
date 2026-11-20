import pytest
from pydantic import ValidationError

from server.app.config import Settings


def test_default_config():
    settings = Settings(SESSION_SECRET="test-secret-at-least-32-chars-long-123456")
    assert settings.VIDEO_PROVIDER in ("ltx-2.3", "gemini-omni-1.2-flash", "mock")
    assert settings.MAX_IMAGES_PER_JOB == 100
    assert settings.MAX_IMAGE_SIZE_BYTES == 20 * 1024 * 1024  # 20 MiB
    assert settings.MAX_PLANNED_SECONDS == 180
    assert settings.RETENTION_DAYS == 2
    assert settings.SESSION_LIFETIME_DAYS == 7


def test_video_provider_validation():
    # Allowed providers
    for p in ["ltx-2.3", "gemini-omni-1.2-flash", "mock"]:
        s = Settings(VIDEO_PROVIDER=p, SESSION_SECRET="test-secret-at-least-32-chars-long-123456")
        assert s.VIDEO_PROVIDER == p

    # Disallowed provider
    with pytest.raises(ValidationError):
        Settings(
            VIDEO_PROVIDER="unsupported-engine",
            SESSION_SECRET="test-secret-at-least-32-chars-long-123456",
        )
