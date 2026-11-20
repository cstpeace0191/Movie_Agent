import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import SourceImage, User
from server.worker.tasks import run_job_sync


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "unused_tester").first()
    if not user:
        user = User(
            username="unused_tester",
            username_lower="unused_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_combined_unused_images(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "Scene A.\n\nScene B."
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00v\x28\xb53"
        + b"\x00" * 50
    )
    # 2 scenes, 3 photos -> 1 unused
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
            data={"scenario": scenario, "provider": "mock"},
            files=files,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["unused_image_count"] == 1
        job_id = data["id"]

        run_job_sync(job_id)

        db = SessionLocal()
        source_imgs = (
            db.query(SourceImage)
            .filter(SourceImage.job_id == job_id)
            .order_by(SourceImage.position)
            .all()
        )
        assert len(source_imgs) == 3
        assert source_imgs[0].used is True
        assert source_imgs[1].used is True
        assert source_imgs[2].used is False
        db.close()
