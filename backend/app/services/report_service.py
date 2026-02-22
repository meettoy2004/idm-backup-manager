import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models.backup_job import BackupJob
from ..models.server import Server
from ..models.notification_setting import NotificationSetting
from .email_service import EmailService

logger = logging.getLogger(__name__)


class ReportService:
    """Generates and emails weekly/monthly backup summary reports"""

    def __init__(self, db: Session):
        self.db    = db
        self.email = EmailService()

    def generate_weekly_report(self) -> dict:
        """Build stats dict for the past 7 days"""
        return self._build_report(days=7, label="Weekly")

    def generate_monthly_report(self) -> dict:
        """Build stats dict for the past 30 days"""
        return self._build_report(days=30, label="Monthly")

    def _build_report(self, days: int, label: str) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        jobs   = self.db.query(BackupJob).filter(BackupJob.started_at >= cutoff).all()

        total    = len(jobs)
        success  = sum(1 for j in jobs if j.status == "SUCCESS")
        failed   = sum(1 for j in jobs if j.status == "FAILED")
        rate     = round((success / total * 100), 1) if total else 0

        # Per-server breakdown
        servers  = self.db.query(Server).filter(Server.is_active == True).all()
        server_stats = []
        for s in servers:
            s_jobs    = [j for j in jobs if j.server_id == s.id]
            s_success = sum(1 for j in s_jobs if j.status == "SUCCESS")
            s_failed  = sum(1 for j in s_jobs if j.status == "FAILED")
            server_stats.append({
                "name":    s.name,
                "total":   len(s_jobs),
                "success": s_success,
                "failed":  s_failed,
            })

        return {
            "label":        label,
            "period_days":  days,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_jobs":   total,
            "successful":   success,
            "failed":       failed,
            "success_rate": rate,
            "servers":      server_stats,
        }

    def send_report(self, report: dict, recipients: List[str]) -> bool:
        """Render report to text + HTML and email it"""
        label     = report['label']
        week_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        text = (
            f"IdM Backup Manager — {label} Report ({week_label})\n"
            f"{'='*50}\n"
            f"Total Jobs:    {report['total_jobs']}\n"
            f"Successful:    {report['successful']}\n"
            f"Failed:        {report['failed']}\n"
            f"Success Rate:  {report['success_rate']}%\n\n"
            f"Per-Server Breakdown:\n"
        )
        for s in report['servers']:
            text += f"  {s['name']}: {s['success']}/{s['total']} OK\n"

        rows = "".join(
            f"<tr><td>{s['name']}</td><td>{s['total']}</td>"
            f"<td style='color:green'>{s['success']}</td>"
            f"<td style='color:{'red' if s['failed'] else 'inherit'}'>{s['failed']}</td></tr>"
            for s in report['servers']
        )
        html = f"""
        <h2>IdM Backup Manager — {label} Report</h2>
        <p><b>Period:</b> Last {report['period_days']} days &nbsp;|&nbsp;
           <b>Generated:</b> {week_label}</p>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:sans-serif">
          <tr style="background:#f3f4f6">
            <th>Metric</th><th>Value</th>
          </tr>
          <tr><td>Total Jobs</td><td>{report['total_jobs']}</td></tr>
          <tr><td>Successful</td><td style="color:green">{report['successful']}</td></tr>
          <tr><td>Failed</td><td style="color:{'red' if report['failed'] else 'inherit'}">{report['failed']}</td></tr>
          <tr><td>Success Rate</td><td><b>{report['success_rate']}%</b></td></tr>
        </table>
        <h3>Per-Server Breakdown</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:sans-serif">
          <tr style="background:#f3f4f6"><th>Server</th><th>Total</th><th>Success</th><th>Failed</th></tr>
          {rows}
        </table>
        """
        return self.email.send_weekly_report(recipients, html, text, f"{label} {week_label}")


def send_weekly_report():
    """Celery task entry point"""
    from ..config.database import SessionLocal
    db = SessionLocal()
    try:
        svc    = ReportService(db)
        report = svc.generate_weekly_report()
        settings_list = db.query(NotificationSetting).filter(
            NotificationSetting.is_enabled == True,
            NotificationSetting.email_addresses != None,
        ).all()
        recipients = list({e for ns in settings_list for e in (ns.email_addresses or [])})
        if recipients:
            svc.send_report(report, recipients)
        else:
            logger.info("Weekly report: no recipients configured")
    finally:
        db.close()


def send_monthly_report():
    """Celery task entry point"""
    from ..config.database import SessionLocal
    db = SessionLocal()
    try:
        svc    = ReportService(db)
        report = svc.generate_monthly_report()
        settings_list = db.query(NotificationSetting).filter(
            NotificationSetting.is_enabled == True,
            NotificationSetting.email_addresses != None,
        ).all()
        recipients = list({e for ns in settings_list for e in (ns.email_addresses or [])})
        if recipients:
            svc.send_report(report, recipients)
        else:
            logger.info("Monthly report: no recipients configured")
    finally:
        db.close()
