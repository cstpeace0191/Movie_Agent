from pathlib import Path

import pytest

from server.worker.providers.base import ProviderError, ShotRequest, ShotResult, VideoProvider
from server.worker.providers.mock import MockVideoProvider


@pytest.fixture
def mock_provider():
    return MockVideoProvider()


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
def test_t2v_request_produces_clip(tmp_path: Path, provider_cls):
    provider: VideoProvider = provider_cls()
    output_path = tmp_path / "shot_0.mp4"
    req = ShotRequest(
        prompt="A peaceful forest during sunrise",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=output_path,
    )
    result = provider.generate(req)
    assert isinstance(result, ShotResult)
    assert result.clip_path.exists()
    assert result.clip_path == output_path
    assert abs(result.duration_seconds - 5.0) <= 0.1
    assert result.width == 832
    assert result.height == 480
    assert result.fps == 16


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
def test_i2v_request_with_image(tmp_path: Path, provider_cls):
    provider: VideoProvider = provider_cls()
    # Create a dummy image
    img_path = tmp_path / "input.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100)

    output_path_i2v = tmp_path / "shot_i2v.mp4"
    req_i2v = ShotRequest(
        prompt="A cat walking in a garden",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=img_path,
        output_path=output_path_i2v,
    )
    result_i2v = provider.generate(req_i2v)
    assert result_i2v.clip_path.exists()

    output_path_t2v = tmp_path / "shot_t2v.mp4"
    req_t2v = ShotRequest(
        prompt="A cat walking in a garden",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=output_path_t2v,
    )
    result_t2v = provider.generate(req_t2v)
    assert result_t2v.clip_path.exists()

    # I2V and T2V outputs should differ
    assert result_i2v.clip_path.read_bytes() != result_t2v.clip_path.read_bytes()


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
@pytest.mark.parametrize("invalid_duration", [0.5, 11.0])
def test_invalid_duration_raises_permanent_error(tmp_path: Path, provider_cls, invalid_duration):
    provider: VideoProvider = provider_cls()
    output_path = tmp_path / "invalid_duration.mp4"
    req = ShotRequest(
        prompt="Invalid duration test",
        duration_seconds=invalid_duration,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=output_path,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.generate(req)
    assert exc_info.value.transient is False
    assert not output_path.exists()


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
def test_missing_source_image_raises_permanent_error(tmp_path: Path, provider_cls):
    provider: VideoProvider = provider_cls()
    non_existent_img = tmp_path / "missing.jpg"
    output_path = tmp_path / "output.mp4"
    req = ShotRequest(
        prompt="Missing image test",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=non_existent_img,
        output_path=output_path,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.generate(req)
    assert exc_info.value.transient is False
    assert not output_path.exists()


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
def test_simulated_timeout_raises_transient_error(tmp_path: Path, monkeypatch, provider_cls):
    provider = provider_cls()
    output_path = tmp_path / "timeout.mp4"
    monkeypatch.setenv("MOCK_SIMULATE_TIMEOUT", "1")
    req = ShotRequest(
        prompt="Simulate timeout",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=output_path,
    )
    with pytest.raises(ProviderError) as exc_info:
        provider.generate(req)
    assert exc_info.value.transient is True
    assert not output_path.exists()


@pytest.mark.parametrize("provider_cls", [MockVideoProvider])
def test_failure_mid_generation_leaves_no_file(tmp_path: Path, monkeypatch, provider_cls):
    provider = provider_cls()
    output_path = tmp_path / "midgen_fail.mp4"
    monkeypatch.setenv("MOCK_FAIL_MIDGEN", "1")
    req = ShotRequest(
        prompt="Simulate midgen failure",
        duration_seconds=5.0,
        width=832,
        height=480,
        fps=16,
        source_image_path=None,
        output_path=output_path,
    )
    with pytest.raises(ProviderError):
        provider.generate(req)
    assert not output_path.exists()
