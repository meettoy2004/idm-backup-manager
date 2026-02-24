import paramiko
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.backup_job import BackupJob
from ..models.server import Server
from ..models.notification_setting import NotificationSetting
from ..config.database import SessionLocal
from ..config import settings
import logging
from .ssh_service import _build_ssh_client

logger = logging.getLogger(__name__)

class JobMonitorService:
    """Monitors IdM servers for completed backup jobs and records them in DB"""

    def _create_ssh_client(self, hostname: str, port: int, username: str) -> Optional[paramiko.SSHClient]:
        """Create SSH connection to IdM server using mounted SSH keys"""
        ssh_key_paths = [
            '/home/appuser/.ssh/id_rsa',
            '/home/appuser/.ssh/id_ed25519',
            '/home/appuser/.ssh/id_ecdsa',
        ]

        client = _build_ssh_client()

        connected = False
        for key_path in ssh_key_paths:
            if not os.path.exists(key_path):
                continue

            for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key):
                try:
                    logger.info("Trying SSH key: %s (%s)", key_path, key_cls.__name__)
                    key = key_cls.from_private_key_file(key_path)
                    client.connect(hostname, port=port, username=username, pkey=key, timeout=30)
                    connected = True
                    logger.info("Connected to %s using %s", hostname, key_path)
                    break
                except paramiko.ssh_exception.SSHException:
                    continue   # wrong key type, try next
                except Exception as exc:
                    logger.debug("Key %s (%s) failed for %s: %s", key_path, key_cls.__name__, hostname, exc)
                    break      # file-level error, try next file
            if connected:
                break

        if not connected:
            # Fallback to ssh-agent / default keys
            try:
                logger.info("Trying default SSH connection to %s", hostname)
                client.connect(hostname, port=port, username=username, timeout=30)
                connected = True
            except Exception as exc:
                logger.error("SSH connection failed to %s: %s", hostname, exc)
                return None

        return client if connected else None

    def poll_server_jobs(self, server: Server, db: Session, since_timestamp: Optional[datetime] = None,
                        full_scan: bool = False) -> List[BackupJob]:
        """SSH to server, query journalctl for ipa-backup.service runs."""
        logger.info("Polling %s (%s)", server.name, server.hostname)
        ssh_client = self._create_ssh_client(server.hostname, server.port, server.username)

        if not ssh_client:
            logger.error("Failed to connect to %s", server.name)
            return []

        try:
            if full_scan:
                since_filter = '--since="90 days ago"'
                logger.info("Full historical scan for %s (last 90 days)", server.name)
            elif since_timestamp:
                since_filter = f'--since="{since_timestamp.strftime("%Y-%m-%d %H:%M:%S")}"'
                logger.info("Incremental scan since %s", since_timestamp)
            else:
                since_filter = '--since="30 days ago"'
                logger.info("First scan for %s (last 30 days)", server.name)

            cmd = f'journalctl -u ipa-backup.service {since_filter} --no-pager -o json'
            logger.info("Running: %s", cmd)

            stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=60)
            journal_json = stdout.read().decode('utf-8')

            if not journal_json.strip():
                logger.info("No journal entries found for %s", server.name)
                ssh_client.close()
                return []

            jobs = self._parse_journal_to_jobs(journal_json, server.id, db)

            ssh_client.close()
            return jobs

        except Exception as exc:
            logger.exception("Error polling %s: %s", server.name, exc)
            try:
                ssh_client.close()
            except Exception:
                pass
            return []

    def _parse_journal_to_jobs(self, journal_json: str, server_id: int, db: Session) -> List[BackupJob]:
        """Parse systemd journal JSON output and create job records"""
        jobs = []
        lines = journal_json.strip().split('\n')

        current_run = None

        for line in lines:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = entry.get('MESSAGE', '')
            timestamp_usec = int(entry.get('__REALTIME_TIMESTAMP', 0))
            timestamp = datetime.fromtimestamp(timestamp_usec / 1_000_000, tz=timezone.utc)

            if 'Starting' in message and ('IdM' in message or 'FreeIPA' in message or 'backup' in message):
                if current_run:
                    self._save_job(current_run, server_id, db, jobs)

                current_run = {
                    'server_id': server_id,
                    'started_at': timestamp,
                    'status': 'RUNNING',
                    'log_output': '',
                }

            if current_run:
                current_run['log_output'] += f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"

            if 'ipa-backup command was successful' in message and current_run:
                current_run['status'] = 'SUCCESS'

            if 'failed' in message.lower() and current_run and current_run['status'] == 'RUNNING':
                current_run['status'] = 'FAILED'
                current_run['error_message'] = message

            if ('Finished' in message or 'Deactivated successfully' in message) and current_run:
                current_run['completed_at'] = timestamp
                self._save_job(current_run, server_id, db, jobs)
                current_run = None

        if current_run:
            logger.warning("Incomplete job run at end of log, marking as FAILED")
            current_run['status'] = 'FAILED'
            current_run['completed_at'] = current_run['started_at']
            self._save_job(current_run, server_id, db, jobs)

        return jobs

    def _save_job(self, run_data: dict, server_id: int, db: Session, jobs_list: List) -> None:
        """Save a job run to database if it doesn't already exist, then send failure alerts."""
        existing = db.query(BackupJob).filter(
            BackupJob.server_id == server_id,
            BackupJob.started_at == run_data['started_at']
        ).first()

        if existing:
            logger.debug("Job already exists: %s", existing.id)
            return

        job = BackupJob(
            server_id=run_data['server_id'],
            status=run_data.get('status', 'FAILED'),
            started_at=run_data['started_at'],
            completed_at=run_data.get('completed_at'),
            log_output=run_data["log_output"][:50000],
            backup_size_bytes=run_data.get("backup_size_bytes"),
            compressed_size_bytes=run_data.get("compressed_size_bytes"),
            error_message=run_data.get('error_message'),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        jobs_list.append(job)
        logger.info("Recorded job %s for server %s: %s at %s", job.id, server_id, job.status, job.started_at)

        # Send failure notification emails if configured
        if job.status == 'FAILED':
            self._send_failure_alerts(job, db)

    def _send_failure_alerts(self, job: BackupJob, db: Session) -> None:
        """Query notification settings and send failure emails."""
        try:
            from .email_service import EmailService
            settings_rows = db.query(NotificationSetting).filter(
                NotificationSetting.notify_on_failure == True,
                NotificationSetting.is_enabled == True,
            ).all()

            if not settings_rows:
                return

            email_svc = EmailService()
            server = db.query(Server).filter(Server.id == job.server_id).first()
            server_name = server.name if server else f"server-{job.server_id}"
            started_at_str = job.started_at.strftime("%Y-%m-%d %H:%M UTC") if job.started_at else "unknown"

            for ns in settings_rows:
                recipients = ns.email_addresses or []
                if not recipients:
                    continue
                email_svc.send_backup_failure(
                    to=recipients,
                    server_name=server_name,
                    job_id=job.id,
                    error_message=job.error_message,
                    started_at=started_at_str,
                )
        except Exception as exc:
            logger.exception("Failed to send failure alert for job %s: %s", job.id, exc)


def poll_all_servers(full_scan: bool = False):
    """Called by background scheduler — polls all active servers for new jobs"""
    db = SessionLocal()
    try:
        monitor = JobMonitorService()
        servers = db.query(Server).filter(Server.is_active == True).all()

        logger.info("==> Polling %d servers for backup jobs (full_scan=%s)", len(servers), full_scan)

        for server in servers:
            last_job = db.query(BackupJob).filter(
                BackupJob.server_id == server.id
            ).order_by(BackupJob.started_at.desc()).first()

            if last_job and not full_scan:
                since = last_job.started_at
                logger.info("Polling %s incrementally since %s", server.name, since)
                new_jobs = monitor.poll_server_jobs(server, db, since_timestamp=since, full_scan=False)
            else:
                logger.info("Polling %s for historical jobs", server.name)
                new_jobs = monitor.poll_server_jobs(server, db, since_timestamp=None, full_scan=full_scan)

            logger.info("Found %d new jobs on %s", len(new_jobs), server.name)

    except Exception as exc:
        logger.exception("Error in poll_all_servers: %s", exc)
    finally:
        db.close()
