import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow


@pytest.mark.asyncio
async def test_reconnect_finished_job():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "reconnect_user").first()
    if not user:
        user = User(
            username="reconnect_user",
            username_lower="reconnect_user",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    now = utcnow()
    job = Job(
        owner_id=user.id,
        input_mode="TEXT_ONLY",
        status="succeeded",
        progress=100,
        message="Finished",
        planned_seconds=5.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    job_id = job.id
    tok, _, _ = create_session(db, user)
    db.close()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok}
    ) as client:
        res = await client.get(f"/api/jobs/{job_id}/events")
        assert res.status_code == 200
        assert "event: done" in res.text or "event: progress" in res.text
