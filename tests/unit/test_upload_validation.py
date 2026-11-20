import pytest

from server.app.storage import StorageValidationError, validate_upload_file


def test_upload_magic_bytes():
    # Valid JPEG
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    media_type, ext = validate_upload_file(jpeg_bytes, "photo.jpg")
    assert media_type == "image/jpeg"
    assert ext == "jpg"

    # Valid PNG with wrong extension (.txt)
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    media_type, ext = validate_upload_file(png_bytes, "photo.txt")
    assert media_type == "image/png"
    assert ext == "png"

    # Valid WebP
    webp_bytes = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 100
    media_type, ext = validate_upload_file(webp_bytes, "photo.webp")
    assert media_type == "image/webp"

    # Unsupported format (e.g. PDF or random bytes)
    with pytest.raises(StorageValidationError) as exc:
        validate_upload_file(b"%PDF-1.4...", "doc.pdf")
    assert exc.value.code == "unsupported_file_type"
    assert "doc.pdf" in exc.value.message


def test_upload_size_limit():
    large_bytes = b"\xff\xd8\xff" + b"\x00" * (20 * 1024 * 1024 + 1)
    with pytest.raises(StorageValidationError) as exc:
        validate_upload_file(large_bytes, "large.jpg")
    assert exc.value.code == "file_too_large"
    assert (
        "20 MB" in exc.value.message or "20 MiB" in exc.value.message or "20" in exc.value.message
    )
