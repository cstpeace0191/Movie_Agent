import subprocess

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.config import settings
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User
from server.worker.pipeline.ffmpeg import get_ffmpeg_cmd
from server.worker.providers.base import ShotRequest, ShotResult
from server.worker.providers.registry import register_provider
from server.worker.tasks import run_job_sync


class CustomMockProvider:
    name = "custom-mock"

    def generate(self, req: ShotRequest) -> ShotResult:
        req.output_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg = get_ffmpeg_cmd()
        cmd = [
            ffmpeg,
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s={req.width}x{req.height}:d={req.duration_seconds}:r={req.fps}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            str(req.output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return ShotResult(
            clip_path=req.output_path,
            duration_seconds=req.duration_seconds,
            width=req.width,
            height=req.height,
            fps=req.fps,
        )


@pytest.fixture
def auth_client():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "swap_tester").first()
    if not user:
        user = User(
            username="swap_tester",
            username_lower="swap_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, csrf_token, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}, csrf_token


@pytest.mark.asyncio
async def test_engine_swap_via_configuration(auth_client, monkeypatch):
    cookies, csrf_token = auth_client
    headers = {"X-CSRF-Token": csrf_token}

    # Register custom provider in the registry
    register_provider("custom-mock", CustomMockProvider)

    # 1. First run with VIDEO_PROVIDER = "mock"
    monkeypatch.setattr(settings, "VIDEO_PROVIDER", "mock")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Submit job with no provider specified in body -> should default to settings.VIDEO_PROVIDER
        res1 = await client.post(
            "/api/jobs", headers=headers, data={"scenario": "First engine test scene."}
        )
        assert res1.status_code == 201
        job1 = res1.json()
        # Check job in database
        db = SessionLocal()
        j1 = db.query(Job).filter(Job.id == job1["id"]).first()
        assert j1 is not None
        assert j1.provider == "mock"
        db.close()

        # Execute job
        run_job_sync(job1["id"])

        # Check video download
        video_res1 = await client.get(f"/api/jobs/{job1['id']}/video")
        assert video_res1.status_code == 200
        assert len(video_res1.content) > 0

    # 2. Swap VIDEO_PROVIDER in configuration without any code change
    monkeypatch.setattr(settings, "VIDEO_PROVIDER", "custom-mock")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        # Submit job with no provider specified -> should now use the new VIDEO_PROVIDER
        res2 = await client.post(
            "/api/jobs", headers=headers, data={"scenario": "Second engine test scene."}
        )
        assert res2.status_code == 201
        job2 = res2.json()

        # Check job in database
        db = SessionLocal()
        j2 = db.query(Job).filter(Job.id == job2["id"]).first()
        assert j2 is not None
        assert j2.provider == "custom-mock"
        db.close()

        # Execute job with swapped provider
        run_job_sync(job2["id"])

        # Check video download succeeds
        video_res2 = await client.get(f"/api/jobs/{job2['id']}/video")
        assert video_res2.status_code == 200
        assert len(video_res2.content) > 0
