import asyncio
import json
import os
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from server.app.auth import require_csrf, require_user
from server.app.config import settings
from server.app.db import SessionLocal, get_db
from server.app.models import Job, Scene, Shot, SourceImage, User, utcnow, validate_alt_text
from server.app.render_options import RenderOptions, RenderOptionsError, parse_render_options
from server.app.schemas import JobOut, JobSummary, ProviderOut, SceneOut, ShotOut, SubtitleLinks
from server.app.storage import (
    StorageValidationError,
    delete_job_media,
    get_image_path,
    validate_upload_file,
)
from server.worker.pipeline.mapping import map_photo_only
from server.worker.pipeline.split import split_by_paragraphs
from server.worker.providers.registry import get_provider_class, is_registered

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/providers", response_model=list[ProviderOut])
async def get_providers(user: User = Depends(require_user)):
    gemini_key = (
        os.getenv("GEMINI_API_KEY") if "GEMINI_API_KEY" in os.environ else settings.GEMINI_API_KEY
    )
    providers: list[ProviderOut] = [
        ProviderOut(
            id="ltx-2.3",
            label="LTX-2.3 (local GPU, default)",
            location="local",
            enabled=True,
            is_default=(settings.VIDEO_PROVIDER == "ltx-2.3"),
            **_capabilities("ltx-2.3"),
            max_clip_seconds=None,
            disabled_reason=None,
        ),
        ProviderOut(
            id="gemini-omni-1.2-flash",
            label="Gemini Omni 1.2 Flash (cloud)",
            location="cloud",
            enabled=bool(gemini_key),
            is_default=(settings.VIDEO_PROVIDER == "gemini-omni-1.2-flash"),
            **_capabilities("gemini-omni-1.2-flash"),
            max_clip_seconds=15.0,
            disabled_reason=None
            if gemini_key
            else "Cloud engine is not configured on this server.",
        ),
    ]
    if settings.ENV == "development" or settings.VIDEO_PROVIDER == "mock" or settings.ENV == "test":
        providers.append(
            ProviderOut(
                id="mock",
                label="Mock Video Engine (dev)",
                location="local",
                enabled=True,
                is_default=(settings.VIDEO_PROVIDER == "mock"),
                **_capabilities("mock"),
                max_clip_seconds=None,
                disabled_reason=None,
            )
        )
    return providers


def _capabilities(name: str) -> dict[str, bool]:
    """Capability flags read from the provider class, never from the engine name (FR-016)."""
    cls = get_provider_class(name)
    return {
        "sends_data_externally": bool(getattr(cls, "sends_data_externally", False)),
        "requires_photos": bool(getattr(cls, "requires_photos", False)),
    }


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(user: User = Depends(require_user), db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.owner_id == user.id).order_by(Job.created_at.desc()).all()
    return [
        JobSummary(
            id=j.id,
            status=j.status,
            input_mode=j.input_mode,
            progress=j.progress,
            message=j.message,
            planned_seconds=j.planned_seconds,
            created_at=j.created_at,
            expires_at=j.expires_at,
            render_options=j.render_options or {},
        )
        for j in jobs
    ]


@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=JobOut)
async def create_job(
    scenario: Annotated[str | None, Form()] = None,
    images: list[UploadFile] = File(default=[]),
    width: Annotated[int, Form()] = 832,
    height: Annotated[int, Form()] = 480,
    seconds_per_shot: Annotated[float, Form()] = 5.0,
    fps: Annotated[int, Form()] = 16,
    provider: Annotated[str | None, Form()] = None,
    chain_frames: Annotated[bool, Form()] = True,
    external_consent: Annotated[bool, Form()] = False,
    include_all_photos: Annotated[bool, Form()] = True,
    image_alt_texts: Annotated[str | None, Form()] = None,
    transition: Annotated[str | None, Form()] = None,
    transition_seconds: Annotated[float | None, Form()] = None,
    caption_position: Annotated[str | None, Form()] = None,
    burn_captions: Annotated[bool | None, Form()] = None,
    captions: Annotated[bool | None, Form()] = None,
    caption_size: Annotated[str | None, Form()] = None,
    caption_color: Annotated[str | None, Form()] = None,
    caption_box: Annotated[bool | None, Form()] = None,
    video_filename: Annotated[str | None, Form()] = None,
    csrf_check: None = Depends(require_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    clean_scenario = scenario.strip() if scenario and scenario.strip() else None

    # Render options (feature 002, FR-042). Validated before any file is stored.
    render_dict: dict[str, Any] = {
        "transition": transition,
        "transition_seconds": transition_seconds,
        "caption_position": caption_position,
        "caption_size": caption_size,
        "caption_color": caption_color,
        "caption_box": caption_box,
        "video_filename": video_filename,
    }
    if caption_position and caption_position != "none":
        render_dict["captions"] = True
        render_dict["burn_captions"] = True
    elif burn_captions is not None:
        render_dict["burn_captions"] = burn_captions
    if captions is not None:
        render_dict["captions"] = captions

    try:
        render_options = parse_render_options(render_dict)
    except RenderOptionsError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_render_option", "message": e.message},
        )

    # Output options validation (FR-014, US5)
    if seconds_per_shot < 1.0 or seconds_per_shot > 10.0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_failed",
                "message": "seconds_per_shot must be between 1.0 and 10.0 seconds.",
            },
        )
    if fps <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "validation_failed", "message": "fps must be positive."},
        )
    if width <= 0 or height <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "validation_failed", "message": "width and height must be positive."},
        )

    # Alt text validation (FR-037)
    parsed_alts: list[str] = []
    if image_alt_texts:
        try:
            parsed_alts = json.loads(image_alt_texts)
            if not isinstance(parsed_alts, list):
                parsed_alts = []
        except Exception:
            parsed_alts = []

        for alt in parsed_alts:
            if not validate_alt_text(alt):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "validation_failed",
                        "message": "Image alt text must be 500 characters or less.",
                    },
                )

    # Check upload image count
    if len(images) > settings.MAX_IMAGES_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "too_many_images",
                "message": f"Upload exceeds maximum of {settings.MAX_IMAGES_PER_JOB} images.",
            },
        )

    if not clean_scenario and not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_input", "message": "At least a scenario or one photo is required."},
        )

    # Determine input mode
    if clean_scenario and images:
        input_mode = "TEXT_IMAGE"
    elif clean_scenario:
        input_mode = "TEXT_ONLY"
    else:
        input_mode = "IMAGE_ONLY"

    # Validate provider
    chosen_provider = provider or settings.VIDEO_PROVIDER
    if not is_registered(chosen_provider):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "unknown_provider",
                "message": f"Provider '{chosen_provider}' is not supported.",
            },
        )

    # Cloud consent check (FR-036), decided by the provider's capability flag
    external_consent_at = None
    if _capabilities(chosen_provider)["sends_data_externally"]:
        if not external_consent:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "consent_required",
                    "message": "Confirmation is required before sending data to cloud AI.",
                },
            )
        external_consent_at = utcnow()

    job_id = str(uuid.uuid4())
    uploaded_files_data = []
    # Validate each image
    for i, img in enumerate(images):
        content = await img.read()
        try:
            media_type, ext = validate_upload_file(content, img.filename or f"image_{i}")
        except StorageValidationError as e:
            st_code = (
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                if e.code == "file_too_large"
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(status_code=st_code, detail={"code": e.code, "message": e.message})

        alt = parsed_alts[i] if i < len(parsed_alts) else None
        img_id = str(uuid.uuid4())
        dest_path = get_image_path(job_id, img_id, ext)
        dest_path.write_bytes(content)
        uploaded_files_data.append((img_id, i, media_type, len(content), str(dest_path), alt))

    # Calculate scenes based on mode
    scenes_data = []
    unused_image_count = 0
    if input_mode == "TEXT_ONLY":
        scenes_data = split_by_paragraphs(clean_scenario, default_duration=seconds_per_shot)
        if not scenes_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "no_input", "message": "Scenario contains no text."},
            )
    elif input_mode == "IMAGE_ONLY":
        img_ids = [u[0] for u in uploaded_files_data]
        scenes_data = map_photo_only(img_ids, duration_seconds=seconds_per_shot)
    else:  # TEXT_IMAGE
        text_scenes = split_by_paragraphs(clean_scenario, default_duration=seconds_per_shot)
        num_scenes = len(text_scenes)
        num_images = len(uploaded_files_data)

        if include_all_photos and num_images > num_scenes:
            # Create a scene for every uploaded photo so no photos are discarded
            unused_image_count = 0
            for idx in range(num_images):
                img_id = uploaded_files_data[idx][0]
                alt_desc = uploaded_files_data[idx][5]
                if idx < num_scenes:
                    desc = text_scenes[idx].description
                elif alt_desc:
                    desc = alt_desc
                elif text_scenes:
                    desc = text_scenes[0].description
                else:
                    desc = f"Scene {idx + 1}"

                from server.worker.pipeline.mapping import MappedScene

                scenes_data.append(
                    MappedScene(
                        position=idx,
                        description=desc,
                        duration_seconds=seconds_per_shot,
                        source_image_id=img_id,
                        split_method="paragraph_extended",
                    )
                )
        else:
            if num_images > num_scenes:
                unused_image_count = num_images - num_scenes

            for idx, ts in enumerate(text_scenes):
                assigned_img_id = uploaded_files_data[idx][0] if idx < num_images else None
                from server.worker.pipeline.mapping import MappedScene

                scenes_data.append(
                    MappedScene(
                        position=idx,
                        description=ts.description,
                        duration_seconds=ts.duration_seconds,
                        source_image_id=assigned_img_id,
                        split_method=ts.split_method,
                    )
                )

    planned_seconds = sum(s.duration_seconds for s in scenes_data)
    if planned_seconds > settings.MAX_PLANNED_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "too_long",
                "message": f"Planned length of {planned_seconds:.1f}s exceeds maximum limit of {settings.MAX_PLANNED_SECONDS}s.",
            },
        )

    now = utcnow()
    expires_at = now + timedelta(days=settings.RETENTION_DAYS)

    job = Job(
        id=job_id,
        owner_id=user.id,
        input_mode=input_mode,
        scenario=clean_scenario,
        status="queued",
        progress=0,
        message="Queued",
        width=width,
        height=height,
        seconds_per_shot=seconds_per_shot,
        fps=fps,
        chain_frames=chain_frames,
        provider=chosen_provider,
        external_consent_at=external_consent_at,
        planned_seconds=planned_seconds,
        unused_image_count=unused_image_count,
        render_options=render_options.to_storage(),
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Save SourceImage rows
    for img_id, pos, m_type, sz, st_path, alt in uploaded_files_data:
        is_used = True
        if input_mode == "TEXT_IMAGE" and pos >= len(scenes_data):
            is_used = False
        src_row = SourceImage(
            id=img_id,
            job_id=job.id,
            position=pos,
            media_type=m_type,
            size_bytes=sz,
            alt_text=alt,
            storage_path=st_path,
            used=is_used,
        )
        db.add(src_row)
    db.commit()

    # Map image_id -> alt text
    image_alt_map = {uid: alt for uid, _, _, _, _, alt in uploaded_files_data if alt}

    from server.worker.pipeline.mapping import DEFAULT_MOTION_PROMPT

    # Save scenes
    for s in scenes_data:
        src_id = getattr(s, "source_image_id", None)
        photo_alt = image_alt_map.get(src_id) if src_id else None
        caption_text = (
            photo_alt
            if photo_alt
            else (s.description if s.description and s.description != DEFAULT_MOTION_PROMPT else None)
        )
        scene_row = Scene(
            job_id=job.id,
            position=s.position,
            description=s.description,
            caption=caption_text,
            caption_source="verbatim" if caption_text else None,
            duration_seconds=s.duration_seconds,
            source_image_id=src_id,
            split_method=s.split_method,
        )
        db.add(scene_row)
    db.commit()

    # Dispatch background task if not running in test mode
    if settings.ENV != "test":
        try:
            from server.worker.tasks import run_job

            run_job.delay(job.id)
        except Exception:
            pass

    return JobOut(
        id=job.id,
        status=job.status,
        input_mode=job.input_mode,
        progress=job.progress,
        message=job.message,
        failure_reason=job.failure_reason,
        planned_seconds=job.planned_seconds,
        unused_image_count=job.unused_image_count,
        created_at=job.created_at,
        expires_at=job.expires_at,
    )


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job not found."},
        )

    shots = db.query(Shot).filter(Shot.job_id == job.id).order_by(Shot.position).all()
    shot_outs: list[ShotOut] = []
    for s in shots:
        excerpt = s.scene.description[:50] if s.scene else None
        shot_outs.append(
            ShotOut(
                id=s.id,
                position=s.position,
                status=s.status,
                attempts=s.attempts,
                scene_excerpt=excerpt,
                source_image_id=s.scene.source_image_id if s.scene else None,
                error=s.error_message,
            )
        )

    return JobOut(
        id=job.id,
        status=job.status,
        input_mode=job.input_mode,
        progress=job.progress,
        message=job.message,
        failure_reason=job.failure_reason,
        planned_seconds=job.planned_seconds,
        unused_image_count=job.unused_image_count,
        created_at=job.created_at,
        expires_at=job.expires_at,
        shots=shot_outs,
        render_options=RenderOptions.from_storage(job.render_options).to_storage(),
        scenes=_scene_outs(db, job),
        text_assist_consented=job.text_assist_consent_at is not None,
        subtitles=SubtitleLinks(
            srt_url=f"/api/jobs/{job.id}/subtitles?format=srt" if job.subtitles_srt_path else None,
            ass_url=f"/api/jobs/{job.id}/subtitles?format=ass" if job.subtitles_ass_path else None,
        ) if (job.subtitles_srt_path or job.subtitles_ass_path) else None,
        music=None,  # filled for library tracks (US4)
        final_duration_seconds=job.final_duration_seconds,
    )


def _scene_outs(db: Session, job: Job) -> list[SceneOut]:
    """Scene list for the job detail, with photo note and alt text (feature 002)."""
    images = {img.id: img for img in db.query(SourceImage).filter(SourceImage.job_id == job.id)}
    scenes = db.query(Scene).filter(Scene.job_id == job.id).order_by(Scene.position).all()
    outs: list[SceneOut] = []
    for sc in scenes:
        img = images.get(sc.source_image_id) if sc.source_image_id else None
        outs.append(
            SceneOut(
                position=sc.position,
                kind=sc.kind or "scene",
                source_image_id=sc.source_image_id,
                image_url=None,  # photo route arrives with the review screen (US2, T040)
                note=img.note if img else None,
                alt_text=img.alt_text if img else None,
                excerpt=(sc.description or "")[:120] or None,
                caption=sc.caption,
                caption_source=sc.caption_source,
                transition=sc.transition,
                start_seconds=sc.start_seconds,
                length_seconds=sc.length_seconds,
            )
        )
    return outs


@router.get("/jobs/{job_id}/events")
async def get_job_events(
    job_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)
):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job not found."},
        )

    async def event_generator():
        last_progress = -1
        last_status = ""
        while True:
            # Poll DB in threadpool or new session
            poll_db = SessionLocal()
            curr = poll_db.query(Job).filter(Job.id == job_id).first()
            if not curr:
                poll_db.close()
                break

            status_val = curr.status
            progress_val = curr.progress
            msg_val = curr.message
            fail_val = curr.failure_reason
            poll_db.close()

            event_payload = {
                "job_id": job_id,
                "status": status_val,
                "progress": progress_val,
                "message": msg_val,
                "failure_reason": fail_val,
            }

            if status_val in ("succeeded", "failed"):
                # Final state
                yield f"event: progress\ndata: {json.dumps(event_payload)}\n\n"
                yield f"event: done\ndata: {json.dumps(event_payload)}\n\n"
                break

            if progress_val != last_progress or status_val != last_status:
                last_progress = progress_val
                last_status = status_val
                yield f"event: progress\ndata: {json.dumps(event_payload)}\n\n"
            else:
                yield ": heartbeat\n\n"

            await asyncio.sleep(1.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    csrf_check: None = Depends(require_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Cancel an active or queued video generation job."""
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job not found."},
        )

    if job.status in ("queued", "running"):
        job.status = "failed"
        job.message = "Generation stopped by user"
        job.failure_reason = "Cancelled by user"
        db.commit()

        # Revoke background Celery task
        try:
            from server.worker.celery_app import celery_app

            celery_app.control.revoke(job_id, terminate=True)
        except Exception:
            pass

        return {"status": "cancelled", "message": "Job generation stopped successfully."}

    return {"status": job.status, "message": f"Job is already {job.status}."}


def schedule_process_shutdown(delay_seconds: float = 1.0) -> None:
    """Send SIGTERM to this process after a short delay, from a daemon thread.

    Kept separate from the route so tests can replace it; patching ``os.kill`` is not enough
    because the thread fires after a test's patch has already been undone.
    """
    import os
    import signal
    import threading
    import time

    def delayed_exit() -> None:
        time.sleep(delay_seconds)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=delayed_exit, daemon=True).start()


@router.post("/system/shutdown")
def shutdown_system(
    csrf_check: None = Depends(require_csrf),
    user: User = Depends(require_user),
):
    """Gracefully initiate server shutdown."""
    schedule_process_shutdown()
    return {"status": "shutting_down", "message": "Application shutdown initiated."}


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    csrf_check: None = Depends(require_csrf),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job not found."},
        )

    if job.status in ("queued", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "job_running", "message": "Cannot delete a queued or running job."},
        )

    delete_job_media(job.id)
    db.delete(job)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/video")
def get_job_video(job_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job or job.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job or video not found."},
        )

    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "failed", "message": f"Job failed: {job.failure_reason}"},
        )
    if (
        job.status != "succeeded"
        or not job.final_video_path
        or not Path(job.final_video_path).exists()
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "not_ready", "message": "Video is not ready yet."},
        )

    # Custom download filename from render_options
    opts = job.render_options or {}
    custom_name = opts.get("video_filename") or opts.get("title")
    if custom_name and str(custom_name).strip():
        safe_name = re.sub(r'[\\/*?:"<>|]', "", str(custom_name).strip()).rstrip(". ")
        if not safe_name.lower().endswith(".mp4"):
            download_name = f"{safe_name}.mp4"
        else:
            download_name = safe_name
    else:
        download_name = f"video_{job.id}.mp4"

    return FileResponse(
        path=job.final_video_path,
        media_type="video/mp4",
        filename=download_name,
    )


@router.get("/jobs/{job_id}/subtitles")
def get_job_subtitles(
    job_id: str,
    format: str = Query("srt", pattern=r"^(srt|ass)$"),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.owner_id == user.id).first()
    if not job or job.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Job not found."},
        )
    sub_path = get_subtitles_path(job.id, format)
    if not sub_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "no_subtitles", "message": "Subtitles not found."},
        )

    return FileResponse(
        path=str(sub_path),
        media_type="text/plain; charset=utf-8",
        filename=f"movie-{job.id}.{format}",
    )
