from datetime import datetime, timezone

from sqlalchemy.orm import Session

from server.app.models import Job


def update_job_progress(
    db: Session,
    job_id: str,
    progress: int | None = None,
    message: str | None = None,
    status: str | None = None,
    failure_reason: str | None = None,
) -> None:
    """Update job progress, clamping to 0-100 and enforcing monotonic increase."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return

    now = datetime.now(timezone.utc)
    job.updated_at = now

    if status is not None:
        job.status = status

    if message is not None:
        job.message = message[:200]

    if failure_reason is not None:
        job.failure_reason = failure_reason[:500]

    if progress is not None:
        # Clamped between 0 and 100, non-decreasing
        clamped = max(0, min(100, progress))
        if clamped >= job.progress:
            job.progress = clamped

    db.commit()
