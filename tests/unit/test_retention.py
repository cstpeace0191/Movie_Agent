from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow
from server.app.storage import get_job_dir
from server.worker.tasks import expire_old_jobs


@pytest.mark.asyncio
async def test_retention_expiration():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "retention_tester").first()
    if not user:
        user = User(
            username="retention_tester",
            username_lower="retention_tester",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Job created 3 days ago (expired)
    old_time = utcnow() - timedelta(days=3)
    job = Job(
        owner_id=user.id,
        input_mode="TEXT_ONLY",
        status="succeeded",
        progress=100,
        message="Done",
        planned_seconds=5.0,
        created_at=old_time,
        updated_at=old_time,
        expires_at=old_time + timedelta(days=2),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id

    # Create dummy media
    jdir = get_job_dir(job_id)
    (jdir / "final.mp4").write_text("video")

    tok, _, _ = create_session(db, user)
    db.close()

    # Run expiration sweep
    expired_count = expire_old_jobs()
    assert expired_count >= 1

    # Verify Job row kept, status is expired, media deleted
    db = SessionLocal()
    refreshed_job = db.query(Job).filter(Job.id == job_id).first()
    assert refreshed_job is not None
    assert refreshed_job.status == "expired"
    assert not jdir.exists()
    db.close()

    # Download returns 404
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok}
    ) as client:
        res = await client.get(f"/api/jobs/{job_id}/video")
        assert res.status_code == 404
