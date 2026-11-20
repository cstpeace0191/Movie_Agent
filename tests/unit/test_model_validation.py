from server.app.models import (
    validate_alt_text,
    validate_job_progress,
    validate_password,
    validate_scene_positions,
    validate_username,
)


def test_username_validation():
    assert validate_username("valid_user_12") is True
    assert validate_username("abc") is True
    assert validate_username("a" * 32) is True

    # Too short (< 3)
    assert validate_username("ab") is False
    # Too long (> 32)
    assert validate_username("a" * 33) is False
    # Invalid characters (hyphen, space, special chars)
    assert validate_username("user-name") is False
    assert validate_username("user name") is False
    assert validate_username("user@name") is False


def test_password_validation():
    # Minimum 12 characters
    assert validate_password("123456789012") is True
    assert validate_password("short") is False
    assert validate_password("12345678901") is False


def test_alt_text_validation():
    assert validate_alt_text(None) is True
    assert validate_alt_text("") is True
    assert validate_alt_text("A beautiful sunset") is True
    assert validate_alt_text("a" * 500) is True
    assert validate_alt_text("a" * 501) is False


def test_job_progress_validation():
    assert validate_job_progress(0) is True
    assert validate_job_progress(50) is True
    assert validate_job_progress(100) is True
    assert validate_job_progress(-1) is False
    assert validate_job_progress(101) is False


def test_scene_positions_validation():
    assert validate_scene_positions([0, 1, 2, 3]) is True
    assert validate_scene_positions([0]) is True
    assert validate_scene_positions([]) is True
    # Non-contiguous or not starting at 0
    assert validate_scene_positions([1, 2, 3]) is False
    assert validate_scene_positions([0, 2, 3]) is False
    assert validate_scene_positions([0, 1, 1, 2]) is False
