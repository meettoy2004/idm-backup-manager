import paramiko
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.backup_job import BackupJob
from ..models.server import Server
from ..config.database import SessionLocal
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class JobMonitorService:
    """Monitors IdM servers for completed backup jobs and records them in DB"""
    
    def _create_ssh_client(self, hostname: str, port: int, username: str) -> Optional[paramiko.SSHClient]:
        """Create SSH connection to IdM server using mounted SSH keys"""
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Try using mounted SSH key from /home/appuser/.ssh/
            ssh_key_paths = [
                '/home/appuser/.ssh/id_rsa',
                '/home/appuser/.ssh/id_ed25519',
                '/home/appuser/.ssh/id_ecdsa',
            ]
            
            connected = False
            for key_path in ssh_key_paths:
                if os.path.exists(key_path):
                    try:
                        logger.info(f"Trying SSH key: {key_path}")
                        key = paramiko.RSAKey.from_private_key_file(key_path)
                        client.connect(hostname, port=port, username=username, pkey=key, timeout=30)
                        connected = True
                        logger.info(f"Connected to {hostname} using {key_path}")
                        break
                    except paramiko.ssh_exception.SSHException:
                        # Try next key type
                        try:
                            key = paramiko.Ed25519Key.from_private_key_file(key_path)
                            client.connect(hostname, port=port, username=username, pkey=key, timeout=30)
                            connected = True
                            logger.info(f"Connected to {hostname} using {key_path}")
                            break
                        except:
                            continue
                    except Exception as e:
                        logger.debug(f"Key {key_path} failed: {e}")
                        continue
            
            if not connected:
                # Fallback to ssh-agent or default
                logger.info(f"Trying default SSH connection to {hostname}")
                client.connect(hostname, port=port, username=username, timeout=30)
                connected = True
            
            if connected:
                return client
            else:
                return None
            
        except Exception as e:
            logger.error(f"SSH connection failed to {hostname}: {e}")
            return None
    
    def poll_server_jobs(self, server: Server, db: Session, since_timestamp: Optional[datetime] = None, 
                        full_scan: bool = False) -> List[BackupJob]:
        """
        SSH to server, query journalctl for ipa-backup.service runs.
        
        Args:
            server: Server model instance
            db: Database session
            since_timestamp: Only get jobs after this time (None = get all)
            full_scan: If True, ignore since_timestamp and get last 90 days
        """
        logger.info(f"Polling {server.name} ({server.hostname})")
        ssh_client = self._create_ssh_client(server.hostname, server.port, server.username)
        
        if not ssh_client:
            logger.error(f"Failed to connect to {server.name}")
            return []
        
        try:
            # Determine time range
            if full_scan:
                # Full historical scan - get last 90 days
                since_filter = '--since="90 days ago"'
                logger.info(f"Full historical scan for {server.name} (last 90 days)")
            elif since_timestamp:
                # Incremental scan - get jobs since last recorded job
                since_filter = f'--since="{since_timestamp.strftime("%Y-%m-%d %H:%M:%S")}"'
                logger.info(f"Incremental scan since {since_timestamp}")
            else:
                # First scan for this server - get last 30 days
                since_filter = '--since="30 days ago"'
                logger.info(f"First scan for {server.name} (last 30 days)")
            
            cmd = f'journalctl -u ipa-backup.service {since_filter} --no-pager -o json'
            logger.info(f"Running: {cmd}")
            
            stdin, stdout, stderr = ssh_client.exec_command(cmd, timeout=60)
            journal_json = stdout.read().decode('utf-8')
            
            if not journal_json.strip():
                logger.info(f"No journal entries found for {server.name}")
                ssh_client.close()
                return []
            
            # Parse journal entries
            jobs = self._parse_journal_to_jobs(journal_json, server.id, db)
            
            ssh_client.close()
            return jobs
            
        except Exception as e:
            logger.error(f"Error polling {server.name}: {e}")
            import traceback
            traceback.print_exc()
            if ssh_client:
                ssh_client.close()
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
            
            # Detect job start
            if 'Starting' in message and ('IdM' in message or 'FreeIPA' in message or 'backup' in message):
                if current_run:
                    # Previous run didn't complete properly, save it as FAILED
                    self._save_job(current_run, server_id, db, jobs)
                
                current_run = {
                    'server_id': server_id,
                    'started_at': timestamp,
                    'status': 'RUNNING',
                    'log_output': '',
                }
            
            # Append all messages to log
            if current_run:
                current_run['log_output'] += f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
            
            # Detect success
            if 'ipa-backup command was successful' in message and current_run:
                current_run['status'] = 'SUCCESS'
            
            # Detect failure
            if 'failed' in message.lower() and current_run and current_run['status'] == 'RUNNING':
                current_run['status'] = 'FAILED'
                current_run['error_message'] = message
            
            # Detect completion
            if ('Finished' in message or 'Deactivated successfully' in message) and current_run:
                current_run['completed_at'] = timestamp
                self._save_job(current_run, server_id, db, jobs)
                current_run = None
        
        # Handle incomplete run at end of log
        if current_run:
            logger.warning(f"Incomplete job run at end of log, marking as FAILED")
            current_run['status'] = 'FAILED'
            current_run['completed_at'] = current_run['started_at']
            self._save_job(current_run, server_id, db, jobs)
        
        return jobs
    
    def _save_job(self, run_data: dict, server_id: int, db: Session, jobs_list: List) -> None:
        """Save a job run to database if it doesn't already exist"""
        # Check if this job already exists in DB
        existing = db.query(BackupJob).filter(
            BackupJob.server_id == server_id,
            BackupJob.started_at == run_data['started_at']
        ).first()
        
        if not existing:
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
            logger.info(f"✓ Recorded job {job.id} for server {server_id}: {job.status} at {job.started_at}")
        else:
            logger.debug(f"Job already exists: {existing.id}")


def poll_all_servers(full_scan: bool = False):
    """
    Called by background scheduler — polls all active servers for new jobs
    
    Args:
        full_scan: If True, do a full 90-day scan regardless of last job timestamp
    """
    db = SessionLocal()
    try:
        monitor = JobMonitorService()
        servers = db.query(Server).filter(Server.is_active == True).all()
        
        logger.info(f"==> Polling {len(servers)} servers for backup jobs (full_scan={full_scan})")
        
        for server in servers:
            # Get last job timestamp for this server
            last_job = db.query(BackupJob).filter(
                BackupJob.server_id == server.id
            ).order_by(BackupJob.started_at.desc()).first()
            
            if last_job and not full_scan:
                # Incremental scan - get jobs since last recorded
                since = last_job.started_at
                logger.info(f"Polling {server.name} incrementally since {since}")
                new_jobs = monitor.poll_server_jobs(server, db, since_timestamp=since, full_scan=False)
            else:
                # First scan or forced full scan - get historical jobs
                logger.info(f"Polling {server.name} for historical jobs")
                new_jobs = monitor.poll_server_jobs(server, db, since_timestamp=None, full_scan=full_scan)
            
            logger.info(f"Found {len(new_jobs)} new jobs on {server.name}")
    
    except Exception as e:
        logger.error(f"Error in poll_all_servers: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
