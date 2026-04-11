"""
Celery application configuration.
Uses Redis as message broker and result backend.
"""

import os
import sys
from celery import Celery

# Add backend to path so workers can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "code_review_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,   # 5 min soft limit
    task_time_limit=600,        # 10 min hard limit
    task_default_queue="code_review",
    task_routes={
        "workers.tasks.analyze_pull_request_task": {"queue": "code_review"},
    },
)

# Auto-discover tasks
celery.autodiscover_tasks(["workers"])
