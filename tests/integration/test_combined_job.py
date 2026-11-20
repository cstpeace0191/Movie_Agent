import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import User
from server.worker.tasks import run_job_sync


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "combined_tester").first()
    if not user:
        user = User(
            username="combined_tester",
            username_lower="combined_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_combined_job_chained(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "Scene 1.\n\nScene 2.\n\nScene 3.\n\nScene 4."
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00v\x28\xb53"
        + b"\x00" * 50
    )
    files = [
        ("images", ("p1.png", png_bytes, "image/png")),
        ("images", ("p2.png", png_bytes, "image/png")),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"scenario": scenario, "provider": "mock", "chain_frames": "true"},
            files=files,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["input_mode"] == "TEXT_IMAGE"
        job_id = data["id"]

        run_job_sync(job_id)

        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["status"] == "succeeded"
        assert len(detail["shots"]) == 4
        assert detail["shots"][0]["source_image_id"] is not None
        assert detail["shots"][1]["source_image_id"] is not None
