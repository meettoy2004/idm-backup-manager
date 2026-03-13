import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from ..models.backup_job import BackupJob
from ..models.server import Server
from ..models.restore_operation import RestoreOperation
from .ssh_service import SSHService
from .audit_service import log_action, AuditAction

logger = logging.getLogger(__name__)

# Allow only safe absolute path characters: letters, digits, /, -, _, .
_SAFE_PATH_RE = re.compile(r'^/[a-zA-Z0-9/_\-\.]+$')

def _validate_path(path: str, label: str = "path") -> str:
    """Reject paths that could enable shell injection or directory traversal."""
    if not path or not _SAFE_PATH_RE.match(path):
        raise ValueError(
            f"Invalid {label}: '{path}'. Only alphanumeric characters, "
            "/, -, _, and . are allowed."
        )
    if ".." in path.split("/"):
        raise ValueError(f"Directory traversal detected in {label}.")
    return path


class RestoreService:
    def __init__(self):
        self.ssh = SSHService()

    def start_restore(self, restore_op: RestoreOperation, db: Session,
                      gpg_passphrase: str) -> RestoreOperation:
        restore_op.restore_status = "running"
        restore_op.started_at = datetime.now(timezone.utc)
        db.commit()

        server = db.query(Server).filter(Server.id == restore_op.server_id).first()
        if not server:
            return self._fail(db, restore_op, "Server not found")

        job = db.query(BackupJob).filter(BackupJob.id == restore_op.job_id).first() if restore_op.job_id else None

        try:
            client = self.ssh.connect(server.hostname, server.port, server.username)
        except Exception as e:
            return self._fail(db, restore_op, f"SSH connect failed: {e}")

        # Use a fixed unique temp file name (no shell variable expansion)
        tmp_file = f"/tmp/idm_restore_{int(time.time())}.tar.gz"

        try:
            # Find backup file
            if job and job.started_at:
                date_str = job.started_at.strftime("%Y-%m-%d")
                find_cmd = f'find /mnt/idm-backup -name "ipa-{date_str}*.tar.gz.gpg" -type f 2>/dev/null | head -1'
            else:
                find_cmd = 'ls -t /mnt/idm-backup/ipa-*.tar.gz.gpg 2>/dev/null | head -1'

            code, backup_file, err = self.ssh.execute_command(client, find_cmd)
            backup_file = backup_file.strip()
            logger.info(f"Found backup file: '{backup_file}'")

            if not backup_file:
                client.close()
                return self._fail(db, restore_op, "No backup file found on server")

            # Validate the server-returned path before embedding in shell commands
            try:
                backup_file = _validate_path(backup_file, "backup_file")
            except ValueError as e:
                client.close()
                return self._fail(db, restore_op, f"Unexpected backup file path from server: {e}")

            raw_restore_path = restore_op.restore_path or "/var/lib/ipa/restore"
            try:
                restore_path = _validate_path(raw_restore_path, "restore_path")
            except ValueError as e:
                client.close()
                return self._fail(db, restore_op, str(e))

            # Ensure restore directory exists
            self.ssh.execute_command(client, f'mkdir -p "{restore_path}"', sudo=True)

            # Step 1: GPG decrypt to fixed temp file
            # Pass passphrase via stdin (--passphrase-fd 0) to avoid exposure in the process list
            decrypt_cmd = (
                f'gpg --batch --yes '
                f'--passphrase-fd 0 '
                f'--no-symkey-cache '
                f'--pinentry-mode loopback '
                f'--output "{tmp_file}" '
                f'--decrypt "{backup_file}"'
            )
            code, out, err = self.ssh.execute_command(
                client, decrypt_cmd, sudo=True, input_data=gpg_passphrase + "\n"
            )
            decrypt_output = (out + err).strip()
            logger.info(f"GPG decrypt exit={code} output={decrypt_output[:200]}")

            if code != 0:
                self.ssh.execute_command(client, f'rm -f "{tmp_file}"', sudo=True)
                client.close()
                return self._fail(db, restore_op, f"GPG decrypt failed (exit {code}): {decrypt_output[:500]}")

            # Step 2: Confirm temp file exists and has size
            code, ls_out, _ = self.ssh.execute_command(client, f'ls -lh "{tmp_file}" 2>&1')
            logger.info(f"Temp file check: {ls_out.strip()}")

            if code != 0:
                client.close()
                return self._fail(db, restore_op, f"Decrypted temp file not found at {tmp_file}")

            # Step 3: Check file type
            _, file_out, _ = self.ssh.execute_command(client, f'file "{tmp_file}"')
            logger.info(f"File type: {file_out.strip()}")

            # Step 4: Extract
            extract_cmd = f'tar -xzf "{tmp_file}" -C "{restore_path}"'
            code, out, err = self.ssh.execute_command(client, extract_cmd, sudo=True)
            extract_output = (out + err).strip()
            logger.info(f"Extract exit={code} output={extract_output[:200]}")

            # Step 5: Cleanup
            self.ssh.execute_command(client, f'rm -f "{tmp_file}"', sudo=True)
            client.close()

            full_output = f"Decrypt: {decrypt_output}\n\nFile: {file_out.strip()}\n\nExtract: {extract_output}"
            restore_op.gpg_decrypt_output = full_output[:10000]

            if code != 0:
                return self._fail(db, restore_op, f"Extract failed (exit {code}): {extract_output[:500]}")

            restore_op.restore_status = "completed"
            restore_op.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(restore_op)
            logger.info(f"Restore {restore_op.id} completed on {server.name} → {restore_path}")
            log_action(db, AuditAction.RESTORE_COMPLETED, user="system",
                resource="restore_operations", resource_id=restore_op.id,
                detail=f"Restore {restore_op.id} completed on server '{server.name}' → {restore_path}")
            return restore_op

        except Exception as e:
            logger.error(f"Restore {restore_op.id} error: {e}")
            try:
                self.ssh.execute_command(client, f'rm -f "{tmp_file}"', sudo=True)
                client.close()
            except: pass
            return self._fail(db, restore_op, str(e))

    def _fail(self, db: Session, restore_op: RestoreOperation, reason: str) -> RestoreOperation:
        restore_op.restore_status = "failed"
        restore_op.error_message  = reason
        restore_op.completed_at   = datetime.now(timezone.utc)
        db.commit()
        db.refresh(restore_op)
        logger.error(f"Restore {restore_op.id} failed: {reason}")
        log_action(db, AuditAction.RESTORE_FAILED, user="system",
            resource="restore_operations", resource_id=restore_op.id,
            detail=f"Restore {restore_op.id} failed: {reason[:500]}",
            status="failure")
        return restore_op
