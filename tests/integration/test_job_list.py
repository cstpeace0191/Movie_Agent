import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow


@pytest.mark.asyncio
async def test_job_list_owner_filter():
    db = SessionLocal()
    # Create two users
    u1 = db.query(User).filter(User.username == "user_one").first()
    if not u1:
        u1 = User(
            username="user_one",
            username_lower="user_one",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u1)
    u2 = db.query(User).filter(User.username == "user_two").first()
    if not u2:
        u2 = User(
            username="user_two",
            username_lower="user_two",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u2)
    db.commit()
    db.refresh(u1)
    db.refresh(u2)

    now = utcnow()
    j1 = Job(
        owner_id=u1.id,
        input_mode="TEXT_ONLY",
        status="queued",
        progress=0,
        message="Queued",
        planned_seconds=5.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    j2 = Job(
        owner_id=u2.id,
        input_mode="TEXT_ONLY",
        status="queued",
        progress=0,
        message="Queued",
        planned_seconds=5.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add_all([j1, j2])
    db.commit()
    db.refresh(j1)
    db.refresh(j2)

    j1_id = j1.id
    j2_id = j2.id

    tok1, _, _ = create_session(db, u1)
    tok2, _, _ = create_session(db, u2)
    db.close()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok1}
    ) as client:
        res = await client.get("/api/jobs")
        assert res.status_code == 200
        jobs = res.json()
        job_ids = [j["id"] for j in jobs]
        assert j1_id in job_ids
        assert j2_id not in job_ids  # Cannot see user 2's jobs

        # Attempting to get user 2's job returns 404
        res2 = await client.get(f"/api/jobs/{j2_id}")
        assert res2.status_code == 404
