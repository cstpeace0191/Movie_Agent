from server.app.db import SessionLocal
from server.app.models import Job, Scene, User, utcnow
from server.worker.tasks import run_job_sync


def test_queue_execution_order(monkeypatch):
    monkeypatch.delenv("MOCK_SIMULATE_TIMEOUT", raising=False)
    monkeypatch.delenv("MOCK_FAIL_SHOTS", raising=False)

    db = SessionLocal()
    user = db.query(User).filter(User.username == "queue_tester").first()
    if not user:
        user = User(username="queue_tester", username_lower="queue_tester", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

    now = utcnow()
    j1 = Job(
        owner_id=user.id,
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
        owner_id=user.id,
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

    s1 = Scene(
        job_id=j1.id,
        position=0,
        description="Scene 1",
        duration_seconds=5.0,
        split_method="paragraph",
    )
    s2 = Scene(
        job_id=j2.id,
        position=0,
        description="Scene 2",
        duration_seconds=5.0,
        split_method="paragraph",
    )
    db.add_all([s1, s2])
    db.commit()

    j1_id = j1.id
    j2_id = j2.id
    db.close()

    # While j1 is run, j2 remains queued
    run_job_sync(j1_id)

    db1 = SessionLocal()
    refreshed_j1 = db1.query(Job).filter(Job.id == j1_id).first()
    refreshed_j2 = db1.query(Job).filter(Job.id == j2_id).first()
    assert refreshed_j1.status in ("succeeded", "failed")
    assert refreshed_j2.status == "queued"
    db1.close()

    # Now run j2
    run_job_sync(j2_id)
    db2 = SessionLocal()
    refreshed_j2_after = db2.query(Job).filter(Job.id == j2_id).first()
    assert refreshed_j2_after.status in ("succeeded", "failed")
    db2.close()
