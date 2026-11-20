import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User
from server.worker.tasks import run_job_sync


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "custom_options_tester").first()
    if not user:
        user = User(
            username="custom_options_tester",
            username_lower="custom_options_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_custom_options_job(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "Scene 1: Introduction.\n\nScene 2: Climax."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={
                "scenario": scenario,
                "width": 640,
                "height": 360,
                "fps": 12,
                "seconds_per_shot": 7.0,
                "provider": "mock",
            },
        )
        assert res.status_code == 201
        job_id = res.json()["id"]

        run_job_sync(job_id)

        db = SessionLocal()
        job = db.query(Job).filter(Job.id == job_id).first()
        assert job.width == 640
        assert job.height == 360
        assert job.fps == 12
        assert job.seconds_per_shot == 7.0
        assert job.status == "succeeded"
        db.close()
