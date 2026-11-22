"""Feature 002, User Story 1: scene transitions and normalized joins (FR-041, FR-042, FR-013)."""

import io
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, Scene, User
from server.worker.pipeline.probe import probe_media
from server.worker.tasks import run_job_sync


@pytest.fixture
def auth():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "transition_tester").first()
    if not user:
        user = User(
            username="transition_tester",
            username_lower="transition_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


def _png(w: int, h: int, color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _photos(sizes):
    colors = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30)]
    return [
        ("images", (f"p{i}.png", _png(w, h, colors[i % 4]), "image/png"))
        for i, (w, h) in enumerate(sizes)
    ]


async def _create_and_run(client, headers, files, data):
    res = await client.post("/api/jobs", headers=headers, data=data, files=files)
    assert res.status_code == 201, res.text
    job_id = res.json()["id"]
    run_job_sync(job_id)
    detail = (await client.get(f"/api/jobs/{job_id}")).json()
    assert detail["status"] == "succeeded", detail
    db = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()
    path = Path(job.final_video_path)
    db.close()
    return detail, probe_media(path)


@pytest.mark.asyncio
async def test_defaults_match_feature_001(auth):
    cookies, headers = auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        detail, info = await _create_and_run(
            client, headers, _photos([(64, 48)] * 3), {"provider": "mock"}
        )
    assert len(detail["scenes"]) == 3
    assert abs(info.duration_seconds - 15.0) <= 0.1
    assert (info.width, info.height) == (832, 480)
    assert info.has_audio is False
    assert detail["render_options"]["transition"] == "none"
    assert [s["start_seconds"] for s in detail["scenes"]] == pytest.approx([0, 5, 10], abs=0.1)


@pytest.mark.asyncio
async def test_fade_shortens_by_overlap_and_records_starts(auth):
    cookies, headers = auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        detail, info = await _create_and_run(
            client,
            headers,
            _photos([(64, 48)] * 3),
            {"provider": "mock", "transition": "fade", "transition_seconds": "1.0"},
        )
    assert abs(info.duration_seconds - 13.0) <= 0.1
    assert [s["start_seconds"] for s in detail["scenes"]] == pytest.approx([0, 4, 8], abs=0.1)
    assert detail["final_duration_seconds"] == pytest.approx(13.0, abs=0.1)
    db = SessionLocal()
    rows = db.query(Scene).filter(Scene.job_id == detail["id"]).order_by(Scene.position).all()
    assert all(r.length_seconds is not None for r in rows)
    db.close()


@pytest.mark.asyncio
async def test_mixed_sizes_produce_one_frame_size(auth):
    cookies, headers = auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Mock renders each clip at the job size; feed different job sizes per clip by
        # using photos of different aspect ratios and a non-default output size.
        detail, info = await _create_and_run(
            client,
            headers,
            _photos([(640, 480), (480, 640), (1280, 400)]),
            {"provider": "mock", "width": "640", "height": "360", "fps": "12"},
        )
    assert (info.width, info.height) == (640, 360)
    assert info.fps == 12


@pytest.mark.asyncio
async def test_invalid_transition_is_rejected(auth):
    cookies, headers = auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        for data, field in (
            ({"provider": "mock", "transition": "spin"}, "transition"),
            ({"provider": "mock", "transition_seconds": "2.5"}, "transition_seconds"),
        ):
            res = await client.post(
                "/api/jobs", headers=headers, data=data, files=_photos([(64, 48)])
            )
            assert res.status_code == 422
            body = res.json()["error"]
            assert body["code"] == "invalid_render_option"
            assert field in body["message"]
