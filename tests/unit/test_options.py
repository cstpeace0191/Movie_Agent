import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import User


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "options_tester").first()
    if not user:
        user = User(
            username="options_tester",
            username_lower="options_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_options_validation_seconds_per_shot(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Too short (< 1.0)
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"scenario": "Scene 1", "seconds_per_shot": 0.5},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "validation_failed"

        # Too long (> 10)
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"scenario": "Scene 1", "seconds_per_shot": 11.0},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "validation_failed"

        # Invalid fps (<= 0)
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"scenario": "Scene 1", "fps": 0},
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "validation_failed"
