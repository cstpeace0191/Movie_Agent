from pathlib import Path

from server.app import storage


def test_new_paths_live_inside_job_dir(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage.settings, "STORAGE_DIR", str(tmp_path))
    job_dir = storage.get_job_dir("job1")
    paths = [
        storage.get_subtitles_path("job1", "srt"),
        storage.get_subtitles_path("job1", "ass"),
        storage.get_bgm_path("job1", "mp3"),
        storage.get_card_path("job1", "title"),
    ]
    assert paths[0].name == "subtitles.srt"
    assert paths[1].name == "subtitles.ass"
    assert paths[2].relative_to(job_dir).as_posix() == "audio/bgm.mp3"
    assert paths[3].relative_to(job_dir).as_posix() == "cards/title.mp4"
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    assert storage.delete_job_media("job1") is True
    assert not any(p.exists() for p in paths)


def test_subtitles_path_rejects_unknown_format(tmp_path: Path, monkeypatch):
    import pytest

    monkeypatch.setattr(storage.settings, "STORAGE_DIR", str(tmp_path))
    with pytest.raises(ValueError):
        storage.get_subtitles_path("job1", "vtt")
