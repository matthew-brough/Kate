from celery import Celery
from celery.signals import worker_process_init

from app.logging_config import configure_logging
from app.settings import settings

celery_app = Celery(
    "kate-worker",
    broker=settings.celery_broker_url,
    include=["app.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)


@worker_process_init.connect
def init_worker(**kwargs: object) -> None:
    configure_logging()
