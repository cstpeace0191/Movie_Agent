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
    user = db.query(User).filter(User.username == "scenario_tester").first()
    if not user:
        user = User(
            username="scenario_tester",
            username_lower="scenario_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}


@pytest.mark.asyncio
async def test_scenario_only_job(auth_headers_and_cookies):
    cookies, headers = auth_headers_and_cookies
    scenario = "Scene 1: Morning in the hills.\n\nScene 2: Sunlight hits the river.\n\nScene 3: Birds flying over trees."

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Submit scenario job
        res = await client.post(
            "/api/jobs",
            headers=headers,
            data={"scenario": scenario, "provider": "mock", "seconds_per_shot": 5.0},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["status"] == "queued"
        job_id = data["id"]
        assert data["planned_seconds"] == 15.0

        # Execute job pipeline synchronously in test
        run_job_sync(job_id)

        # Get job detail
        res = await client.get(f"/api/jobs/{job_id}")
        assert res.status_code == 200
        detail = res.json()
        assert detail["status"] == "succeeded"
        assert detail["progress"] == 100
        assert len(detail["shots"]) == 3
        for shot in detail["shots"]:
            assert shot["status"] == "succeeded"

        # Download finished video
        res = await client.get(f"/api/jobs/{job_id}/video")
        assert res.status_code == 200
        assert res.headers["content-type"] == "video/mp4"
        assert len(res.content) > 0
