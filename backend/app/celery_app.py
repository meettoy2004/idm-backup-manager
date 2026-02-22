from celery import Celery
from celery.schedules import crontab
from .config import settings

celery_app = Celery(
    "idm-backup-manager",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    'poll-backup-jobs-every-5-min': {
        'task': 'app.tasks.poll_backup_jobs',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}

celery_app.autodiscover_tasks(['app.tasks'])
