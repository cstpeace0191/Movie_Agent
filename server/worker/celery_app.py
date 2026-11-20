from celery import Celery
from celery.schedules import crontab

from server.app.config import settings

celery_app = Celery(
    "movie_agent_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["server.worker.tasks"],
)

celery_app.conf.update(
    worker_concurrency=1,  # FR-026: one job at a time per GPU
    task_time_limit=settings.TASK_TIME_LIMIT_SECONDS,  # FR-025: per-task timeout
    task_soft_time_limit=settings.TASK_TIME_LIMIT_SECONDS - 30,
    task_track_started=True,
    broker_connection_retry_on_startup=False,
    broker_connection_max_retries=1,
    redis_socket_connect_timeout=0.5,
    redis_socket_timeout=0.5,
    beat_schedule={
        # Hourly retention sweep (R12, T083)
        "hourly-retention-sweep": {
            "task": "expire_old_jobs_task",
            "schedule": crontab(minute=0),
        },
    },
)
