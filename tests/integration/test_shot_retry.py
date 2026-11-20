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
    user = db.query(User).filter(User.username == "retry_tester").first()
    if not user:
        user = User(
            username="retry_tester",
            username_lower="retry_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_shot_retry_once_succeeds(auth_headers_and_cookies, monkeypatch):
    cookies, headers = auth_headers_and_cookies
    monkeypatch.setenv("MOCK_FAIL_SHOTS", "1:1")  # Shot 1 fails on attempt 1, succeeds on attempt 2
    scenario = "Scene 0: Introduction.\n\nScene 1: Action sequence."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        res = await client.post(
            "/api/jobs", headers=headers, data={"scenario": scenario, "provider": "mock"}
        )
        assert res.status_code == 201
        job_id = res.json()["id"]

        run_job_sync(job_id)

        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["status"] == "succeeded"
        assert detail["shots"][1]["attempts"] == 2


@pytest.mark.asyncio
async def test_shot_retry_twice_fails_job(auth_headers_and_cookies, monkeypatch):
    cookies, headers = auth_headers_and_cookies
    monkeypatch.setenv("MOCK_FAIL_SHOTS", "1:1,1:2")  # Shot 1 fails on both attempts
    scenario = "Scene 0: Introduction.\n\nScene 1: Action sequence."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        res = await client.post(
            "/api/jobs", headers=headers, data={"scenario": scenario, "provider": "mock"}
        )
        assert res.status_code == 201
        job_id = res.json()["id"]

        run_job_sync(job_id)

        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["status"] == "failed"
        assert "shot 1" in detail["failure_reason"].lower()
