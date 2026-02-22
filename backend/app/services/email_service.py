import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Sends email notifications via SMTP"""

    def __init__(self):
        self.smtp_host     = getattr(settings, 'SMTP_HOST', 'localhost')
        self.smtp_port     = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_user     = getattr(settings, 'SMTP_USER', '')
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')
        self.smtp_from     = getattr(settings, 'SMTP_FROM', 'idm-backup@localhost')
        self.use_tls       = getattr(settings, 'SMTP_TLS', True)

    def send(self, to: List[str], subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """Send an email. Returns True on success."""
        if not to:
            logger.warning("send() called with empty recipient list — skipping")
            return False

        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = self.smtp_from
        msg['To']      = ', '.join(to)

        msg.attach(MIMEText(body, 'plain'))
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        try:
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=10)

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.smtp_from, to, msg.as_string())
            server.quit()
            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    def send_backup_failure(self, to: List[str], server_name: str, job_id: int,
                             error_message: Optional[str], started_at: str) -> bool:
        subject = f"[IdM Backup] FAILED — {server_name}"
        body = (
            f"Backup job #{job_id} FAILED on {server_name}\n\n"
            f"Started:  {started_at}\n"
            f"Error:    {error_message or 'Unknown error'}\n\n"
            f"Log in to the IdM Backup Manager for details."
        )
        html_body = f"""
        <h2 style="color:#dc2626">Backup Failed — {server_name}</h2>
        <table style="border-collapse:collapse;font-family:monospace">
          <tr><td style="padding:4px 12px 4px 0"><b>Job ID</b></td><td>#{job_id}</td></tr>
          <tr><td style="padding:4px 12px 4px 0"><b>Server</b></td><td>{server_name}</td></tr>
          <tr><td style="padding:4px 12px 4px 0"><b>Started</b></td><td>{started_at}</td></tr>
          <tr><td style="padding:4px 12px 4px 0"><b>Error</b></td><td style="color:#dc2626">{error_message or 'Unknown error'}</td></tr>
        </table>
        <p>Log in to the <a href="#">IdM Backup Manager</a> for full details.</p>
        """
        return self.send(to, subject, body, html_body)

    def send_backup_success(self, to: List[str], server_name: str, job_id: int,
                             duration_seconds: Optional[float], backup_size_bytes: Optional[int]) -> bool:
        size_str = f"{backup_size_bytes / 1_048_576:.1f} MB" if backup_size_bytes else "N/A"
        dur_str  = f"{duration_seconds:.0f}s" if duration_seconds else "N/A"
        subject  = f"[IdM Backup] OK — {server_name}"
        body = (
            f"Backup job #{job_id} completed successfully on {server_name}\n\n"
            f"Duration: {dur_str}\n"
            f"Size:     {size_str}\n"
        )
        return self.send(to, subject, body)

    def send_weekly_report(self, to: List[str], report_html: str, report_text: str,
                            week_label: str) -> bool:
        subject = f"[IdM Backup] Weekly Report — {week_label}"
        return self.send(to, subject, report_text, report_html)
