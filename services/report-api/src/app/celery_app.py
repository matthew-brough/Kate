from celery import Celery

from app.settings import settings

celery_app = Celery(
    "kate-worker",
    broker=settings.effective_celery_broker_url,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
)
