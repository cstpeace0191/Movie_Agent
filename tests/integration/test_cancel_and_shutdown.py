from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User, utcnow


@pytest.mark.asyncio
async def test_cancel_job_workflow():
    db = SessionLocal()
    u1 = db.query(User).filter(User.username == "cancel_user_1").first()
    if not u1:
        u1 = User(
            username="cancel_user_1",
            username_lower="cancel_user_1",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u1)
    u2 = db.query(User).filter(User.username == "cancel_user_2").first()
    if not u2:
        u2 = User(
            username="cancel_user_2",
            username_lower="cancel_user_2",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u2)
    db.commit()
    db.refresh(u1)
    db.refresh(u2)

    now = utcnow()
    j_run = Job(
        owner_id=u1.id,
        input_mode="TEXT_ONLY",
        status="running",
        progress=30,
        message="Generating shot 1/3",
        planned_seconds=6.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add(j_run)
    db.commit()
    db.refresh(j_run)
    j_id = j_run.id

    token_u1, csrf_u1, _ = create_session(db, u1)
    token_u2, csrf_u2, _ = create_session(db, u2)
    db.close()

    transport = ASGITransport(app=app)
    # 1. Unauthenticated cancel -> 401
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(f"/api/jobs/{j_id}/cancel")
        assert res.status_code == 401

    # 2. Cancel by other user -> 404
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"movie_session": token_u2}
    ) as ac:
        res = await ac.post(
            f"/api/jobs/{j_id}/cancel",
            headers={"X-CSRF-Token": csrf_u2},
        )
        assert res.status_code == 404

    # 3. Cancel by owner -> 200
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"movie_session": token_u1}
    ) as ac:
        res = await ac.post(
            f"/api/jobs/{j_id}/cancel",
            headers={"X-CSRF-Token": csrf_u1},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "cancelled"

    db2 = SessionLocal()
    j_db = db2.query(Job).filter(Job.id == j_id).first()
    assert j_db is not None
    assert j_db.status == "failed"
    assert j_db.failure_reason == "Cancelled by user"
    db2.close()


@pytest.mark.asyncio
async def test_system_shutdown_endpoint():
    db = SessionLocal()
    u = db.query(User).filter(User.username == "shutdown_user").first()
    if not u:
        u = User(
            username="shutdown_user",
            username_lower="shutdown_user",
            password_hash=hash_password("pwd123456789"),
        )
        db.add(u)
        db.commit()
        db.refresh(u)

    token, csrf_token, _ = create_session(db, u)
    db.close()

    transport = ASGITransport(app=app)
    # 1. Unauthenticated -> 401
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/system/shutdown")
        assert res.status_code == 401

    # 2. With auth and CSRF, mock os.kill to avoid killing test process
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies={"movie_session": token}
    ) as ac:
        with patch("os.kill"):
            res = await ac.post(
                "/api/system/shutdown",
                headers={"X-CSRF-Token": csrf_token},
            )
            assert res.status_code == 200
            assert res.json()["status"] == "shutting_down"
