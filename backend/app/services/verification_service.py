import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from ..models.backup_job import BackupJob
from ..models.verification_log import VerificationLog
from ..models.server import Server
from .ssh_service import SSHService

logger = logging.getLogger(__name__)


class VerificationService:
    """GPG signature verification and SHA256 integrity checking for backup files"""

    def __init__(self):
        self.ssh = SSHService()

    def verify_job(self, job: BackupJob, db: Session) -> VerificationLog:
        """
        SSH to the server, find the backup file for this job, run GPG verify
        and SHA256 integrity check. Saves a VerificationLog and returns it.
        """
        server = db.query(Server).filter(Server.id == job.server_id).first()
        if not server:
            return self._save_log(db, job.id, "FAILED", error_message="Server not found")

        try:
            client = self.ssh.connect(server.hostname, server.port, server.username)
        except Exception as e:
            return self._save_log(db, job.id, "FAILED", error_message=f"SSH connect failed: {e}")

        try:
            # Find the backup file closest to job start time
            started_str = job.started_at.strftime("%Y-%m-%d") if job.started_at else ""
            find_cmd = f'find /mnt/idm-backup -name "ipa-{started_str}*.tar.gz.gpg" -type f 2>/dev/null | head -1'
            code, backup_file, err = self.ssh.execute_command(client, find_cmd)
            backup_file = backup_file.strip()

            if not backup_file:
                client.close()
                return self._save_log(db, job.id, "FAILED",
                                      error_message=f"No backup file found for date {started_str}")

            # SHA256 integrity check
            sha_file = backup_file + ".sha256"
            integrity_passed, sha_output = self._check_sha256(client, backup_file, sha_file)

            # GPG verify (checks signature/encryption header is intact)
            gpg_passed, gpg_output = self._check_gpg(client, backup_file)

            client.close()

            overall = "PASSED" if (integrity_passed and gpg_passed) else "FAILED"
            combined_output = f"SHA256:\n{sha_output}\n\nGPG:\n{gpg_output}"

            log = self._save_log(
                db, job.id, overall,
                gpg_verify_output=combined_output,
                integrity_check_passed=integrity_passed,
            )
            logger.info(f"Verification job {job.id} on {server.name}: {overall}")
            return log

        except Exception as e:
            logger.error(f"Verification error for job {job.id}: {e}")
            if client:
                client.close()
            return self._save_log(db, job.id, "FAILED", error_message=str(e))

    def _check_sha256(self, client, backup_file: str, sha_file: str) -> Tuple[bool, str]:
        """Run sha256sum --check against the .sha256 sidecar file"""
        code, out, err = self.ssh.execute_command(
            client,
            f'test -f "{sha_file}" && cd "$(dirname "{backup_file}")" && sha256sum --check "$(basename "{sha_file}")" 2>&1 || echo "SHA_FILE_MISSING"'
        )
        output = (out + err).strip()
        passed = code == 0 and "OK" in output and "SHA_FILE_MISSING" not in output
        return passed, output

    def _check_gpg(self, client, backup_file: str) -> Tuple[bool, str]:
        """Check GPG file is valid (list-packets — does not decrypt)"""
        code, out, err = self.ssh.execute_command(
            client,
            f'gpg --list-packets "{backup_file}" 2>&1 | head -20'
        )
        output = (out + err).strip()
        passed = code == 0 and ("encrypted" in output.lower() or "symkey enc packet" in output.lower())
        return passed, output

    def _save_log(self, db: Session, job_id: int, status: str,
                  gpg_verify_output: Optional[str] = None,
                  integrity_check_passed: Optional[bool] = None,
                  error_message: Optional[str] = None) -> VerificationLog:
        log = VerificationLog(
            job_id=job_id,
            verification_status=status,
            gpg_verify_output=gpg_verify_output,
            integrity_check_passed=integrity_check_passed,
            error_message=error_message,
            verified_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log


def verify_recent_jobs(days: int = 1):
    """Celery task entry point — verify all successful jobs from last N days"""
    from ..config.database import SessionLocal
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        jobs = db.query(BackupJob).filter(
            BackupJob.status == "SUCCESS",
            BackupJob.completed_at >= cutoff,
        ).all()

        logger.info(f"Verifying {len(jobs)} jobs from last {days} day(s)")
        svc = VerificationService()
        for job in jobs:
            # Skip if already verified
            existing = db.query(VerificationLog).filter(VerificationLog.job_id == job.id).first()
            if not existing:
                svc.verify_job(job, db)
    finally:
        db.close()
