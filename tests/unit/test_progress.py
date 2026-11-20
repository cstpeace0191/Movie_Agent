from datetime import datetime, timezone

from server.app.db import SessionLocal
from server.app.models import Job
from server.worker.pipeline.progress import update_job_progress


def test_progress_monotonic_and_bounds():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    job = Job(
        owner_id="dummy_owner",
        input_mode="TEXT_ONLY",
        status="running",
        progress=0,
        message="Starting",
        planned_seconds=15.0,
        created_at=now,
        updated_at=now,
        expires_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Valid increase
    update_job_progress(db, job.id, progress=25, message="Generating shot 1/3")
    db.refresh(job)
    assert job.progress == 25
    assert job.message == "Generating shot 1/3"

    # Attempt decrease should clamp to current progress (non-decreasing)
    update_job_progress(db, job.id, progress=10, message="Stage change")
    db.refresh(job)
    assert job.progress == 25  # did not regress
    assert job.message == "Stage change"

    # Clamp > 100
    update_job_progress(db, job.id, progress=120, message="Completed")
    db.refresh(job)
    assert job.progress == 100

    db.delete(job)
    db.commit()
    db.close()
