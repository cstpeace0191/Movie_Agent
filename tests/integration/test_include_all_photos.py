import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Scene, User
from server.worker.tasks import run_job_sync


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "include_all_tester").first()
    if not user:
        user = User(
            username="include_all_tester",
            username_lower="include_all_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_include_all_photos_with_single_paragraph(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "단일 문단 제목입니다."
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00v\x28\xb53"
        + b"\x00" * 50
    )
    # 3 photos, but only 1 paragraph scenario
    files = [
        ("images", ("p1.png", png_bytes, "image/png")),
        ("images", ("p2.png", png_bytes, "image/png")),
        ("images", ("p3.png", png_bytes, "image/png")),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={
                "scenario": scenario,
                "provider": "mock",
                "seconds_per_shot": "1.0",
                "include_all_photos": "true",
            },
            files=files,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["unused_image_count"] == 0
        assert data["planned_seconds"] == 3.0
        job_id = data["id"]

        run_job_sync(job_id)

        db = SessionLocal()
        scenes = db.query(Scene).filter(Scene.job_id == job_id).order_by(Scene.position).all()
        assert len(scenes) == 3
        # All 3 scenes have source_image_id
        for s in scenes:
            assert s.source_image_id is not None
        db.close()
