import json

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
    user = db.query(User).filter(User.username == "photo_tester").first()
    if not user:
        user = User(
            username="photo_tester",
            username_lower="photo_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_photo_only_job(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x06\x00\x00\x00v\x28\xb53"
        + b"\x00" * 50
    )

    files = [
        ("images", ("photo1.png", png_bytes, "image/png")),
        ("images", ("photo2.png", png_bytes, "image/png")),
        ("images", ("photo3.png", png_bytes, "image/png")),
    ]
    alt_texts = json.dumps(["A cute kitten", "A running puppy", "A soaring eagle"])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Test 501 chars alt text rejection
        too_long_alts = json.dumps(["a" * 501, "short", "short"])
        bad_res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"image_alt_texts": too_long_alts},
            files=files,
        )
        assert bad_res.status_code == 422
        assert bad_res.json()["error"]["code"] == "validation_failed"

        # Valid photo job submission
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"image_alt_texts": alt_texts, "provider": "mock"},
            files=files,
        )
        assert res.status_code == 201
        data = res.json()
        assert data["input_mode"] == "IMAGE_ONLY"
        job_id = data["id"]

        run_job_sync(job_id)

        # Check job detail
        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["status"] == "succeeded"
        assert len(detail["shots"]) == 3
        for shot in detail["shots"]:
            assert shot["source_image_id"] is not None

        # Verify SourceImage rows in DB
        db = SessionLocal()
        source_imgs = (
            db.query(SourceImage)
            .filter(SourceImage.job_id == job_id)
            .order_by(SourceImage.position)
            .all()
        )
        assert len(source_imgs) == 3
        assert source_imgs[0].alt_text == "A cute kitten"
        assert source_imgs[1].alt_text == "A running puppy"
        assert source_imgs[2].alt_text == "A soaring eagle"
        db.close()
