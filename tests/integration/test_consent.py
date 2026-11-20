import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "consent_tester").first()
    if not user:
        user = User(
            username="consent_tester",
            username_lower="consent_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_cloud_consent_requirement(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "Scene with cloud AI"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # 1. Cloud provider without consent -> 422 consent_required
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={
                "scenario": scenario,
                "provider": "gemini-omni-1.2-flash",
                "external_consent": "false",
            },
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "consent_required"

        # 2. Cloud provider with consent -> 201 and external_consent_at recorded
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={
                "scenario": scenario,
                "provider": "gemini-omni-1.2-flash",
                "external_consent": "true",
            },
        )
        assert res.status_code == 201
        job_id = res.json()["id"]

        db = SessionLocal()
        job = db.query(Job).filter(Job.id == job_id).first()
        assert job.external_consent_at is not None
        db.close()
