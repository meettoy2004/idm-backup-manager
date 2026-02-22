import logging
from typing import List, Tuple
from sqlalchemy.orm import Session
from ..models.server import Server
from ..models.backup_config import BackupConfig
from .ssh_service import SSHService

logger = logging.getLogger(__name__)


class S3CleanupService:
    """Deletes old backup files from S3 mount on each server based on retention_count"""

    def __init__(self):
        self.ssh = SSHService()

    def cleanup_server(self, server: Server, config: BackupConfig) -> Tuple[int, List[str]]:
        """
        SSH to server, list backup files, delete oldest beyond retention_count.
        Returns (deleted_count, list_of_deleted_filenames).
        """
        try:
            client = self.ssh.connect(server.hostname, server.port, server.username)
        except Exception as e:
            logger.error(f"S3 cleanup SSH failed for {server.name}: {e}")
            return 0, []

        deleted_files = []
        try:
            s3_dir = config.s3_mount_dir or "/mnt/idm-backup"

            # List all .gpg backup files sorted oldest first
            code, out, err = self.ssh.execute_command(
                client,
                f'ls -1t "{s3_dir}"/ipa-*.tar.gz.gpg 2>/dev/null'
            )
            files = [f.strip() for f in out.strip().splitlines() if f.strip()]

            if len(files) <= config.retention_count:
                logger.info(f"{server.name}: {len(files)} files, retention={config.retention_count} — nothing to delete")
                client.close()
                return 0, []

            # Files to delete = everything beyond retention_count (list is newest-first)
            to_delete = files[config.retention_count:]
            logger.info(f"{server.name}: deleting {len(to_delete)} old backup(s)")

            for f in to_delete:
                sha_file = f + ".sha256"
                # Delete both the .gpg and .sha256 sidecar
                del_cmd = f'rm -f "{f}" "{sha_file}"'
                code, _, err = self.ssh.execute_command(client, del_cmd, sudo=True)
                if code == 0:
                    deleted_files.append(f)
                    logger.info(f"Deleted: {f}")
                else:
                    logger.warning(f"Failed to delete {f}: {err}")

            client.close()
            return len(deleted_files), deleted_files

        except Exception as e:
            logger.error(f"S3 cleanup error on {server.name}: {e}")
            if client:
                client.close()
            return 0, []


def run_s3_cleanup():
    """Celery task entry point — run cleanup on all active servers"""
    from ..config.database import SessionLocal

    db = SessionLocal()
    try:
        configs = db.query(BackupConfig).filter(BackupConfig.is_enabled == True).all()
        svc = S3CleanupService()
        total_deleted = 0

        for config in configs:
            server = db.query(Server).filter(
                Server.id == config.server_id,
                Server.is_active == True
            ).first()
            if not server:
                continue
            deleted, files = svc.cleanup_server(server, config)
            total_deleted += deleted
            logger.info(f"{server.name}: cleaned up {deleted} file(s)")

        logger.info(f"S3 cleanup complete — total deleted: {total_deleted}")
    finally:
        db.close()
