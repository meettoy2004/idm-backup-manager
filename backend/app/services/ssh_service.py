import paramiko
import os
import logging
from typing import Tuple, Optional
from ..config import settings

logger = logging.getLogger(__name__)

KNOWN_HOSTS_PATH = "/home/appuser/.ssh/known_hosts"


def _build_ssh_client() -> paramiko.SSHClient:
    """Create an SSHClient with host-key verification where possible.

    If a known_hosts file exists it is loaded and RejectPolicy is used —
    only pre-approved host keys will be accepted.  When no known_hosts file
    is present we fall back to AutoAddPolicy and log a security warning so
    operators know they should provision known_hosts.
    """
    client = paramiko.SSHClient()
    if os.path.exists(KNOWN_HOSTS_PATH):
        client.load_host_keys(KNOWN_HOSTS_PATH)
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
        logger.debug(f"SSH: loaded known_hosts from {KNOWN_HOSTS_PATH}, using RejectPolicy")
    else:
        logger.warning(
            "SSH: no known_hosts file found at %s — falling back to AutoAddPolicy. "
            "Mount a known_hosts file to enable host-key verification and prevent MITM attacks.",
            KNOWN_HOSTS_PATH,
        )
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    return client


class SSHService:
    def __init__(self):
        # Use mounted SSH keys instead of Vault
        self.ssh_key_path = "/home/appuser/.ssh/id_rsa"

    def get_ssh_key(self) -> Tuple[str, Optional[str]]:
        """Retrieve SSH private key from mounted volume"""
        if not os.path.exists(self.ssh_key_path):
            raise FileNotFoundError(f"SSH key not found at {self.ssh_key_path}")

        with open(self.ssh_key_path, "r") as f:
            private_key_str = f.read()

        return private_key_str, None

    def connect(self, hostname: str, port: int = 22, username: Optional[str] = None) -> paramiko.SSHClient:
        """Establish SSH connection to remote server using mounted SSH keys"""
        if not username:
            raise ValueError("Username is required for SSH connection")

        client = _build_ssh_client()

        key_paths = [
            "/home/appuser/.ssh/id_rsa",
            "/home/appuser/.ssh/id_ed25519",
            "/home/appuser/.ssh/id_ecdsa",
        ]

        connected = False
        for key_path in key_paths:
            if not os.path.exists(key_path):
                continue

            # Try RSA first, then Ed25519
            for key_cls in (paramiko.RSAKey, paramiko.Ed25519Key):
                try:
                    key = key_cls.from_private_key_file(key_path)
                    client.connect(
                        hostname=hostname,
                        port=port,
                        username=username,
                        pkey=key,
                        timeout=30,
                        look_for_keys=False,
                        allow_agent=False,
                    )
                    connected = True
                    logger.info("SSH connected to %s using %s (%s)", hostname, key_path, key_cls.__name__)
                    break
                except paramiko.ssh_exception.SSHException:
                    # Wrong key type for this file — try next type
                    continue
                except Exception as exc:
                    logger.debug("SSH key %s (%s) failed for %s: %s", key_path, key_cls.__name__, hostname, exc)
                    break   # file-level error, move to next key file
            if connected:
                break

        if not connected:
            raise Exception(f"Failed to connect to {hostname} with any available SSH keys")

        return client

    def execute_command(
        self,
        client: paramiko.SSHClient,
        command: str,
        sudo: bool = False,
        input_data: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """Execute command on remote server"""
        if sudo:
            command = f"sudo {command}"

        stdin, stdout, stderr = client.exec_command(command, timeout=300)

        if input_data:
            stdin.write(input_data)
            stdin.flush()

        stdin.close()

        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")

        return exit_code, output, error
