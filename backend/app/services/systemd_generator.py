from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from typing import Dict
import secrets

class SystemdGenerator:
    def __init__(self):
        template_dir = Path(__file__).parent.parent.parent / "templates" / "systemd"
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
    
    def generate_encryption_key(self) -> str:
        """Generate a random 128-byte encryption key"""
        return secrets.token_urlsafe(128)
    
    def generate_backup_service(self, config: Dict[str, str]) -> str:
        """Generate ipa-backup.service file content"""
        template = self.env.get_template('ipa-backup.service.j2')
        return template.render(**config)
    
    def generate_backup_timer(self, config: Dict[str, str]) -> str:
        """Generate ipa-backup.timer file content"""
        template = self.env.get_template('ipa-backup.timer.j2')
        return template.render(**config)
    
    def generate_retention_service(self, config: Dict[str, str]) -> str:
        """Generate ipa-backup-retention.service file content"""
        template = self.env.get_template('ipa-backup-retention.service.j2')
        return template.render(**config)
    
    def generate_retention_script(self, config: Dict[str, str]) -> str:
        """Generate ipa-backup-retention.sh script content"""
        template = self.env.get_template('ipa-backup-retention.sh.j2')
        return template.render(**config)
    
    def generate_security_profile(self, config: Dict[str, str]) -> str:
        """Generate zz_shh-profile.conf file content"""
        template = self.env.get_template('zz_shh-profile.conf.j2')
        return template.render(**config)
    
    def generate_all_files(self, config: Dict[str, str]) -> Dict[str, str]:
        """Generate all systemd files and return as dictionary"""
        return {
            'ipa-backup.service': self.generate_backup_service(config),
            'ipa-backup.timer': self.generate_backup_timer(config),
            'ipa-backup-retention.service': self.generate_retention_service(config),
            'ipa-backup-retention.sh': self.generate_retention_script(config),
            'zz_shh-profile.conf': self.generate_security_profile(config)
        }
