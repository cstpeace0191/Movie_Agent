import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import Job, User

BASELINE_FILE = Path(__file__).parent / "latency_baseline.json"
MAX_P95_MS = 300.0
REGRESSION_TOLERANCE = 0.10  # 10% maximum regression


@pytest.fixture
def perf_user_and_job():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "latency_tester").first()
    if not user:
        user = User(
            username="latency_tester",
            username_lower="latency_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    job = db.query(Job).filter(Job.owner_id == user.id).first()
    if not job:
        job = Job(
            owner_id=user.id,
            input_mode="TEXT_ONLY",
            status="succeeded",
            progress=100,
            planned_seconds=5.0,
            provider="mock",
            expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

    raw_token, csrf_token, _ = create_session(db, user)
    job_id = job.id
    db.close()
    return {"movie_session": raw_token}, csrf_token, job_id


async def measure_endpoint(
    client: AsyncClient,
    method: str,
    url: str,
    headers: dict | None = None,
    concurrency: int = 5,
    iterations: int = 10,
) -> float:
    async def single_call():
        t0 = time.perf_counter()
        if method == "GET":
            res = await client.get(url, headers=headers)
        elif method == "POST":
            res = await client.post(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method {method}")
        assert res.status_code in (200, 201)
        return (time.perf_counter() - t0) * 1000.0  # in ms

    # Warm-up request
    try:
        await single_call()
    except Exception:
        pass

    latencies: list[float] = []
    # Run batches with 5 concurrent requests
    for _ in range(iterations):
        batch = [single_call() for _ in range(concurrency)]
        results = await asyncio.gather(*batch)
        latencies.extend(results)

    latencies.sort()
    # 95th percentile index
    p95_idx = int(0.95 * len(latencies))
    return latencies[p95_idx]


@pytest.mark.asyncio
async def test_non_generation_latency_budget(perf_user_and_job):
    cookies, csrf_token, job_id = perf_user_and_job
    endpoints = [
        ("health", "GET", "/api/health", None, False),
        ("providers", "GET", "/api/providers", None, True),
        ("auth_me", "GET", "/api/auth/me", None, True),
        ("jobs_list", "GET", "/api/jobs", None, True),
        ("job_detail", "GET", f"/api/jobs/{job_id}", None, True),
    ]

    measured: dict[str, float] = {}

    for name, method, url, hdrs, use_auth in endpoints:
        c = cookies if use_auth else None
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", cookies=c
        ) as client:
            p95 = await measure_endpoint(client, method, url, hdrs, concurrency=5, iterations=8)
            measured[name] = round(p95, 2)
            # Budget check: p95 must be <= 300ms
            assert p95 <= MAX_P95_MS, (
                f"Endpoint {name} p95 latency {p95}ms exceeds budget {MAX_P95_MS}ms"
            )

    # Baseline file comparison and regression gate
    if not BASELINE_FILE.exists():
        # Initialize baseline file
        BASELINE_FILE.write_text(json.dumps(measured, indent=2), encoding="utf-8")
    else:
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        for ep_name, measured_p95 in measured.items():
            if ep_name in baseline:
                base_p95 = baseline[ep_name]
                # Fail if more than 10% above baseline, with a small absolute jitter margin (10ms)
                max_allowed = max(base_p95 * (1.0 + REGRESSION_TOLERANCE), base_p95 + 10.0)
                assert measured_p95 <= max_allowed, (
                    f"Regression detected on {ep_name}: measured {measured_p95}ms > "
                    f"allowed {max_allowed:.2f}ms (baseline: {base_p95}ms + 10%)"
                )
