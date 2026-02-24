from .celery_app import celery_app
from .services.job_monitor_service import poll_all_servers
import logging

logger = logging.getLogger(__name__)

@celery_app.task(
    name='app.tasks.poll_backup_jobs',
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,          # exponential backoff between retries
    retry_backoff_max=60,        # cap backoff at 60 seconds
    retry_jitter=True,           # add randomness to avoid thundering herd
    time_limit=600,              # hard kill after 10 min if SSH hangs
    soft_time_limit=540,         # soft kill at 9 min so we can clean up
)
def poll_backup_jobs(self):
    """Background task: poll all IdM servers for completed backup jobs"""
    logger.info("Starting backup job poll...")
    try:
        poll_all_servers()
    except Exception as exc:
        logger.exception("poll_backup_jobs failed (attempt %d/%d): %s",
                         self.request.retries + 1, self.max_retries + 1, exc)
        raise   # triggers autoretry
    logger.info("Backup job poll complete.")
    return "OK"
