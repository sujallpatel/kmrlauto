from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "kmrl_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_ack_late=True,  # Task acknowledgment on completion
    worker_prefetch_multiplier=1,  # Fair task distribution
    task_routes={
        "workers.tasks.process_document_task": {"queue": "document_processing"}
    }
)
