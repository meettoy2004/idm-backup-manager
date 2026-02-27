from .ssh_service import SSHService
from .systemd_generator import SystemdGenerator
import hvac
from typing import Dict, Tuple
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class DeploymentService:
    def __init__(self):
        self.ssh_service = SSHService()
        self.systemd_generator = SystemdGenerator()
        self.vault_client = hvac.Client(
            url=settings.VAULT_ADDR,
            token=settings.VAULT_TOKEN
        )
    
    def deploy_backup_configuration(
        self, 
        hostname: str,
        port: int,
        username: str,
        config: Dict[str, str],
        server_name: str = None
    ) -> Tuple[bool, str]:
        try:
            logger.info(f"Connecting to {hostname}:{port}")
            ssh_client = self.ssh_service.connect(hostname, port, username)
            
            # Generate encryption key
            encryption_key = self.systemd_generator.generate_encryption_key()
            
            # Generate all systemd files
            files = self.systemd_generator.generate_all_files(config)
            
            # Step 1: Create backup directories
            logger.info("Creating backup directories...")
            self._execute_command(ssh_client, f"mkdir -p {config['s3_mount_dir']}")
            self._execute_command(ssh_client, f"mkdir -p {config['s3_mount_dir']}/_invalid")
            self._execute_command(ssh_client, f"mkdir -p {config['backup_dir']}")
            
            # Step 2: Deploy retention script
            logger.info("Deploying retention script...")
            self._deploy_file(
                ssh_client,
                "/var/lib/ipa/ipa-backup-retention.sh",
                files['ipa-backup-retention.sh'],
                mode="755",
                selinux_context="bin_t"
            )
            
            # Step 3: Deploy systemd unit files
            logger.info("Deploying systemd unit files...")
            self._deploy_file(
                ssh_client,
                "/etc/systemd/system/ipa-backup.service",
                files['ipa-backup.service']
            )
            self._deploy_file(
                ssh_client,
                "/etc/systemd/system/ipa-backup.timer",
                files['ipa-backup.timer']
            )
            self._deploy_file(
                ssh_client,
                "/etc/systemd/system/ipa-backup-retention.service",
                files['ipa-backup-retention.service']
            )
            
            # Step 4: Deploy security profile
            logger.info("Deploying security profile...")
            self._execute_command(
                ssh_client,
                "mkdir -p /etc/systemd/system/ipa-backup-retention.service.d"
            )
            self._deploy_file(
                ssh_client,
                "/etc/systemd/system/ipa-backup-retention.service.d/zz_shh-profile.conf",
                files['zz_shh-profile.conf']
            )
            
            # Step 5: Create encrypted credential on server
            logger.info("Creating encrypted credential...")
            self._create_encrypted_credential(ssh_client, encryption_key)
            
            # Step 6: Store encryption key in Vault for recovery
            logger.info("Storing encryption key in Vault...")
            vault_path = f"backup-keys/{server_name or hostname}"
            self._store_key_in_vault(
                vault_path=vault_path,
                encryption_key=encryption_key,
                hostname=hostname,
                server_name=server_name,
                config=config
            )
            
            # Step 7: Reload systemd and enable services
            logger.info("Reloading systemd and enabling services...")
            self._execute_command(ssh_client, "systemctl daemon-reload")
            # Enable units so they start on boot
            self._execute_command(ssh_client, "systemctl enable ipa-backup.timer")
            self._execute_command(ssh_client, "systemctl enable ipa-backup.service")
            self._execute_command(ssh_client, "systemctl enable ipa-backup-retention.service")
            # Restart the timer so the new OnCalendar schedule takes effect immediately.
            # 'enable --now' is a no-op if the timer is already running; 'restart' is required.
            self._execute_command(ssh_client, "systemctl restart ipa-backup.timer")
            
            # Step 8: Verify deployment
            logger.info("Verifying deployment...")
            exit_code, output, error = self.ssh_service.execute_command(
                ssh_client,
                "systemctl list-unit-files | grep ipa-backup",
                sudo=True
            )
            logger.info(f"Unit files:\n{output}")
            
            ssh_client.close()
            
            logger.info(f"Successfully deployed to {hostname}")
            return True, f"Deployment successful. Encryption key stored in Vault at secret/{vault_path}"
            
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            return False, f"Deployment failed: {str(e)}"
    
    def _store_key_in_vault(
        self,
        vault_path: str,
        encryption_key: str,
        hostname: str,
        server_name: str,
        config: Dict
    ):
        """Store encryption key securely in Vault using KV v2"""
        try:
            self.vault_client.secrets.kv.v2.create_or_update_secret(
                path=vault_path,
                mount_point='secret',
                secret={
                    'encryption_key': encryption_key,
                    'hostname': hostname,
                    'server_name': server_name or hostname,
                    'backup_dir': config.get('backup_dir', ''),
                    's3_mount_dir': config.get('s3_mount_dir', ''),
                    'schedule': config.get('schedule', ''),
                    'note': 'Required to decrypt backups from this server. Keep secure!'
                }
            )
            logger.info(f"Encryption key stored in Vault at secret/{vault_path}")
        except Exception as e:
            logger.error(f"Failed to store key in Vault: {str(e)}")
            raise Exception(f"Failed to store encryption key in Vault: {str(e)}")
    
    def get_encryption_key(self, server_name: str) -> str:
        """Retrieve encryption key from Vault for a specific server"""
        try:
            vault_path = f"backup-keys/{server_name}"
            secret = self.vault_client.secrets.kv.v2.read_secret_version(
                path=vault_path,
                mount_point='secret'
            )
            return secret['data']['data']['encryption_key']
        except Exception as e:
            raise Exception(f"Failed to retrieve encryption key from Vault: {str(e)}")

    def _execute_command(self, ssh_client, command: str) -> Tuple[int, str, str]:
        exit_code, output, error = self.ssh_service.execute_command(
            ssh_client,
            command,
            sudo=True
        )
        if exit_code != 0:
            raise Exception(f"Command failed: {command}\nError: {error}")
        return exit_code, output, error
    
    def _deploy_file(
        self,
        ssh_client,
        remote_path: str,
        content: str,
        mode: str = "644",
        selinux_context: str = None
    ):
        self.ssh_service.execute_command(
            ssh_client,
            f"tee {remote_path}",
            sudo=True,
            input_data=content
        )
        self._execute_command(ssh_client, f"chmod {mode} {remote_path}")
        if selinux_context:
            self._execute_command(ssh_client, f"chcon -t {selinux_context} {remote_path}")
    
    def _create_encrypted_credential(self, ssh_client, encryption_key: str):
        # Write key via stdin to avoid shell interpolation / command injection
        self.ssh_service.execute_command(
            ssh_client,
            "tee /tmp/backup_pw.txt > /dev/null",
            sudo=True,
            input_data=encryption_key,
        )
        exit_code, encrypted_output, error = self.ssh_service.execute_command(
            ssh_client,
            "systemd-creds encrypt --name=backup-encryption-password -p /tmp/backup_pw.txt -",
            sudo=True
        )
        if exit_code != 0:
            raise Exception(f"Failed to encrypt credential: {error}")
        
        self._execute_command(
            ssh_client,
            "mkdir -p /etc/systemd/system/ipa-backup.service.d"
        )
        credential_config = f"[Service]\n{encrypted_output}"
        self.ssh_service.execute_command(
            ssh_client,
            "tee /etc/systemd/system/ipa-backup.service.d/ipa-bkp-secret.conf",
            sudo=True,
            input_data=credential_config
        )
        self._execute_command(
            ssh_client,
            "chmod 600 /etc/systemd/system/ipa-backup.service.d/ipa-bkp-secret.conf"
        )
        self._execute_command(
            ssh_client,
            "chown root:root /etc/systemd/system/ipa-backup.service.d/ipa-bkp-secret.conf"
        )
        self._execute_command(
            ssh_client,
            "chmod 750 /etc/systemd/system/ipa-backup.service.d"
        )
        self._execute_command(ssh_client, "rm -f /tmp/backup_pw.txt")
