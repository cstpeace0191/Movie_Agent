import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import User


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "test_val_user").first()
    if not user:
        user = User(
            username="test_val_user",
            username_lower="test_val_user",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_job_validation_no_input(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # No scenario and no images
        res = await client.post("/api/jobs", headers=headers, data={})
        assert res.status_code == 400
        data = res.json()
        assert data["error"]["code"] == "no_input"


@pytest.mark.asyncio
async def test_job_validation_too_long(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # 40 scenes x 5 seconds = 200 seconds > 180 max
        long_scenario = "\n\n".join([f"Paragraph {i}" for i in range(40)])
        res = await client.post(
            "/api/jobs", headers=headers, data={"scenario": long_scenario, "seconds_per_shot": 5.0}
        )
        assert res.status_code == 422
        data = res.json()
        assert data["error"]["code"] == "too_long"
        assert "180" in data["error"]["message"]
