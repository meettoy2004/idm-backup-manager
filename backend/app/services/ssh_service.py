import paramiko
import os
from typing import Tuple, Optional
from ..config import settings

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
        
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key_paths = [
            "/home/appuser/.ssh/id_rsa",
            "/home/appuser/.ssh/id_ed25519",
            "/home/appuser/.ssh/id_ecdsa"
        ]
        
        connected = False
        for key_path in key_paths:
            if not os.path.exists(key_path):
                continue
                
            try:
                key = paramiko.RSAKey.from_private_key_file(key_path)
                client.connect(hostname=hostname, port=port, username=username, pkey=key, timeout=30, look_for_keys=False, allow_agent=False)
                connected = True
                break
            except:
                try:
                    key = paramiko.Ed25519Key.from_private_key_file(key_path)
                    client.connect(hostname=hostname, port=port, username=username, pkey=key, timeout=30, look_for_keys=False, allow_agent=False)
                    connected = True
                    break
                except:
                    continue
        
        if not connected:
            raise Exception(f"Failed to connect to {hostname} with any available SSH keys")
        
        return client
    
    def execute_command(self, client: paramiko.SSHClient, command: str, sudo: bool = False, input_data: Optional[str] = None) -> Tuple[int, str, str]:
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
