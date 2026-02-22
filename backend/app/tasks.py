from .celery_app import celery_app
from .services.job_monitor_service import poll_all_servers
import logging

logger = logging.getLogger(__name__)

@celery_app.task(name='app.tasks.poll_backup_jobs')
def poll_backup_jobs():
    """Background task: poll all IdM servers for completed backup jobs"""
    logger.info("Starting backup job poll...")
    poll_all_servers()
    logger.info("Backup job poll complete.")
    return "OK"
