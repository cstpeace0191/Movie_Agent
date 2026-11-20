from server.app.db import SessionLocal
from server.app.models import Job, Scene, User, utcnow
from server.worker.tasks import run_job_sync


def test_job_time_limit_timeout(monkeypatch):
    db = SessionLocal()
    user = db.query(User).filter(User.username == "timeout_tester").first()
    if not user:
        user = User(
            username="timeout_tester", username_lower="timeout_tester", password_hash="hash"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    now = utcnow()
    job = Job(
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
    db.add(job)
    db.commit()
    db.refresh(job)

    scene = Scene(
        job_id=job.id,
        position=0,
        description="Scene timing out",
        duration_seconds=5.0,
        split_method="paragraph",
    )
    db.add(scene)
    db.commit()

    job_id = job.id
    db.close()

    # Force simulated timeout
    monkeypatch.setenv("MOCK_SIMULATE_TIMEOUT", "1")
    run_job_sync(job_id)

    db = SessionLocal()
    refreshed_job = db.query(Job).filter(Job.id == job_id).first()
    assert refreshed_job.status == "failed"
    assert "timeout" in refreshed_job.failure_reason.lower()
    db.close()
