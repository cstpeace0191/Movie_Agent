import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow
from server.app.storage import get_job_dir


@pytest.mark.asyncio
async def test_delete_job_workflow():
    db = SessionLocal()
    u1 = db.query(User).filter(User.username == "del_user_1").first()
    if not u1:
        u1 = User(
            username="del_user_1",
            username_lower="del_user_1",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u1)
    u2 = db.query(User).filter(User.username == "del_user_2").first()
    if not u2:
        u2 = User(
            username="del_user_2",
            username_lower="del_user_2",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u2)
    db.commit()
    db.refresh(u1)
    db.refresh(u2)

    now = utcnow()
    # Completed job for u1
    j_done = Job(
        owner_id=u1.id,
        input_mode="TEXT_ONLY",
        status="succeeded",
        progress=100,
        message="Done",
        planned_seconds=5.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    # Running job for u1
    j_run = Job(
        owner_id=u1.id,
        input_mode="TEXT_ONLY",
        status="running",
        progress=50,
        message="Running",
        planned_seconds=5.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add_all([j_done, j_run])
    db.commit()
    db.refresh(j_done)
    db.refresh(j_run)

    j_done_id = j_done.id
    j_run_id = j_run.id

    # Create dummy media file
    job_media_dir = get_job_dir(j_done_id)
    (job_media_dir / "test.mp4").write_text("dummy")

    tok1, csrf1, _ = create_session(db, u1)
    tok2, csrf2, _ = create_session(db, u2)
    db.close()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok1}
    ) as client:
        # 1. DELETE without CSRF -> 403 csrf_failed
        res = await client.delete(f"/api/jobs/{j_done_id}")
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "csrf_failed"

        # 2. DELETE running job -> 409 job_running
        res = await client.delete(f"/api/jobs/{j_run_id}", headers={"X-CSRF-Token": csrf1})
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "job_running"

    # 3. DELETE other user's job -> 404
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok2}
    ) as client:
        res = await client.delete(f"/api/jobs/{j_done_id}", headers={"X-CSRF-Token": csrf2})
        assert res.status_code == 404

    # 4. DELETE successful job -> 204 and removes media
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies={"movie_session": tok1}
    ) as client:
        res = await client.delete(f"/api/jobs/{j_done_id}", headers={"X-CSRF-Token": csrf1})
        assert res.status_code == 204
        assert not job_media_dir.exists()
