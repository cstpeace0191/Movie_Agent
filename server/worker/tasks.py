from datetime import datetime, timezone
from pathlib import Path

from server.app.db import SessionLocal
from server.app.models import Job, Scene, Shot, SourceImage
from server.app.storage import delete_job_media, get_final_video_path, get_shot_path
from server.worker.celery_app import celery_app
from server.worker.pipeline.frames import extract_last_frame
from server.worker.pipeline.join import join_shots
from server.worker.pipeline.progress import update_job_progress
from server.worker.providers.base import ProviderError, ShotRequest
from server.worker.providers.registry import get_provider


def resolve_provider(provider_name: str):
    """Resolve a provider name to a VideoProvider instance, falling back to mock."""
    try:
        return get_provider(provider_name)
    except Exception:
        return get_provider("mock")


def expire_old_jobs() -> int:
    """Sweep database for expired jobs, delete their stored media, and mark status expired."""
    db = SessionLocal()
    count = 0
    try:
        now = datetime.now(timezone.utc)
        jobs = db.query(Job).filter(Job.expires_at < now, Job.status != "expired").all()
        for job in jobs:
            delete_job_media(job.id)
            job.status = "expired"
            job.final_video_path = None
            count += 1
        db.commit()
    finally:
        db.close()
    return count


def run_job_sync(job_id: str) -> None:
    """Execute the end-to-end video generation pipeline synchronously for a job."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        update_job_progress(db, job_id, status="running", progress=5, message="Starting generation")

        scenes = db.query(Scene).filter(Scene.job_id == job_id).order_by(Scene.position).all()
        if not scenes:
            update_job_progress(
                db, job_id, status="failed", failure_reason="No scenes found for job"
            )
            return

        provider = resolve_provider(job.provider)
        shot_paths: list[Path] = []
        total_scenes = len(scenes)
        last_clip_path: Path | None = None

        for i, scene in enumerate(scenes):
            # Check cancellation before starting next shot
            job_check = db.query(Job).filter(Job.id == job_id).first()
            if not job_check or (
                job_check.status == "failed" and job_check.failure_reason == "Cancelled by user"
            ):
                return

            shot = db.query(Shot).filter(Shot.job_id == job_id, Shot.position == i).first()
            if not shot:
                shot = Shot(
                    job_id=job_id,
                    scene_id=scene.id,
                    position=i,
                    status="generating",
                    attempts=0,
                )
                db.add(shot)
                db.commit()
                db.refresh(shot)

            shot_output_path = get_shot_path(job_id, i)
            source_img_path = None
            if scene.source_image_id:
                src_img = (
                    db.query(SourceImage).filter(SourceImage.id == scene.source_image_id).first()
                )
                if src_img:
                    source_img_path = Path(src_img.storage_path)
            elif job.chain_frames and last_clip_path and last_clip_path.exists():
                frame_path = shot_output_path.parent / f"frame_prev_{i}.png"
                extract_last_frame(last_clip_path, frame_path, width=job.width, height=job.height)
                source_img_path = frame_path

            shot_req = ShotRequest(
                prompt=scene.description,
                duration_seconds=scene.duration_seconds,
                width=job.width,
                height=job.height,
                fps=job.fps,
                source_image_path=source_img_path,
                output_path=shot_output_path,
            )

            # Generate with 1 automatic retry (FR-033)
            success = False
            last_error = ""
            for attempt in range(1, 3):  # Attempts 1 and 2
                shot.attempts = attempt
                db.commit()

                pct = int(10 + (i / total_scenes) * 75)
                update_job_progress(
                    db,
                    job_id,
                    progress=pct,
                    message=f"Generating shot {i + 1}/{total_scenes}"
                    + (f" (retry {attempt})" if attempt > 1 else ""),
                )

                try:
                    res = provider.generate(shot_req)
                    shot.status = "succeeded"
                    shot.clip_path = str(res.clip_path)
                    db.commit()
                    shot_paths.append(res.clip_path)
                    last_clip_path = res.clip_path
                    success = True
                    break
                except ProviderError as e:
                    last_error = e.message
                    if attempt == 2:
                        shot.status = "failed"
                        shot.error_message = last_error
                        db.commit()
                except Exception as e:
                    last_error = str(e)
                    if attempt == 2:
                        shot.status = "failed"
                        shot.error_message = last_error
                        db.commit()

            if not success:
                update_job_progress(
                    db,
                    job_id,
                    status="failed",
                    failure_reason=f"Shot {i} failed: {last_error}",
                )
                return

        # All shots generated, now join
        update_job_progress(db, job_id, progress=90, message="Joining video shots")
        final_video_path = get_final_video_path(job_id)
        join_shots(shot_paths, final_video_path, width=job.width, height=job.height, fps=job.fps)

        job.final_video_path = str(final_video_path)
        update_job_progress(
            db, job_id, status="succeeded", progress=100, message="Video generation complete"
        )
    finally:
        db.close()


@celery_app.task(bind=True, name="run_job")
def run_job(self, job_id: str):
    run_job_sync(job_id)


@celery_app.task(name="expire_old_jobs_task")
def expire_old_jobs_task():
    return expire_old_jobs()


@celery_app.task(name="send_verification_email_task")
def send_verification_email_task(to_email: str, code: str, username: str) -> bool:
    """Asynchronous Celery task for dispatching verification emails."""
    from server.app.email_sender import send_verification_email

    return send_verification_email(to_email=to_email, code=code, username=username)
