import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow


@pytest.fixture
def auth_headers_and_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "sse_tester").first()
    if not user:
        user = User(
            username="sse_tester",
            username_lower="sse_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    user_id = user.id
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, {"X-CSRF-Token": csrf_token}, user_id


@pytest.mark.asyncio
async def test_sse_events_stream(auth_headers_and_cookies):
    cookies, headers, user_id = auth_headers_and_cookies
    db = SessionLocal()
    now = utcnow()
    job = Job(
        owner_id=user_id,
        input_mode="TEXT_ONLY",
        status="succeeded",
        progress=100,
        message="Done",
        planned_seconds=10.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Request events stream
        res = await client.get(f"/api/jobs/{job_id}/events")
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        text = res.text
        assert "event: progress" in text or "event: done" in text
