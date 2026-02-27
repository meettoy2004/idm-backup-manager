from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ...config.database import get_db
from ...models.system_setting import SystemSetting

router = APIRouter()


# ── helpers ──────────────────────────────────────────────────────────────────

def _get(db: Session, key: str, default: str = "") -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else default


def _set(db: Session, key: str, value: str):
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


# ── schema ────────────────────────────────────────────────────────────────────

class SmtpConfig(BaseModel):
    smtp_host:     str  = "localhost"
    smtp_port:     int  = 587
    smtp_user:     str  = ""
    smtp_password: str  = ""   # empty string means "no change" when it equals the mask
    smtp_from:     str  = "idm-backup@localhost"
    smtp_tls:      bool = True


_MASK = "••••••••"


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/smtp")
def get_smtp_config(db: Session = Depends(get_db)):
    from ...config import settings
    has_password = bool(_get(db, "smtp_password") or settings.SMTP_PASSWORD)
    return {
        "smtp_host":     _get(db, "smtp_host")     or settings.SMTP_HOST,
        "smtp_port":     int(_get(db, "smtp_port") or settings.SMTP_PORT),
        "smtp_user":     _get(db, "smtp_user")     or settings.SMTP_USER,
        "smtp_password": _MASK if has_password else "",
        "smtp_from":     _get(db, "smtp_from")     or settings.SMTP_FROM,
        "smtp_tls":      _get(db, "smtp_tls", "true").lower() == "true",
    }


@router.put("/smtp")
def update_smtp_config(config: SmtpConfig, db: Session = Depends(get_db)):
    _set(db, "smtp_host", config.smtp_host)
    _set(db, "smtp_port", str(config.smtp_port))
    _set(db, "smtp_user", config.smtp_user)
    _set(db, "smtp_from", config.smtp_from)
    _set(db, "smtp_tls",  "true" if config.smtp_tls else "false")
    # Only update password if a real value was supplied (not the mask)
    if config.smtp_password and config.smtp_password != _MASK:
        _set(db, "smtp_password", config.smtp_password)
    db.commit()
    return {"message": "SMTP settings saved"}


@router.post("/smtp/test")
def test_smtp_config(db: Session = Depends(get_db)):
    from ...config import settings
    from ...services.email_service import EmailService

    svc = EmailService()
    svc.smtp_host     = _get(db, "smtp_host")     or settings.SMTP_HOST
    svc.smtp_port     = int(_get(db, "smtp_port") or settings.SMTP_PORT)
    svc.smtp_user     = _get(db, "smtp_user")     or settings.SMTP_USER
    svc.smtp_password = _get(db, "smtp_password") or settings.SMTP_PASSWORD
    svc.smtp_from     = _get(db, "smtp_from")     or settings.SMTP_FROM
    svc.use_tls       = _get(db, "smtp_tls", "true").lower() == "true"

    to = [svc.smtp_user] if svc.smtp_user else []
    if not to:
        raise HTTPException(status_code=400, detail="No recipient: set smtp_user to a valid address first")

    ok = svc.send(to, "[IDM Toolkit] SMTP Test", "SMTP configuration is working correctly.")
    return {"success": ok, "message": "Test email sent" if ok else "Failed to send — check logs"}


# ── Security policies ─────────────────────────────────────────────────────────

class SecurityConfig(BaseModel):
    session_timeout_minutes:  int = 60
    lockout_threshold:        int = 5
    lockout_duration_minutes: int = 15
    lockout_reset_minutes:    int = 10


@router.get("/security")
def get_security_config(db: Session = Depends(get_db)):
    return {
        "session_timeout_minutes":  int(_get(db, "security_session_timeout_minutes",  "60")),
        "lockout_threshold":        int(_get(db, "security_lockout_threshold",         "5")),
        "lockout_duration_minutes": int(_get(db, "security_lockout_duration_minutes",  "15")),
        "lockout_reset_minutes":    int(_get(db, "security_lockout_reset_minutes",     "10")),
    }


@router.put("/security")
def update_security_config(config: SecurityConfig, db: Session = Depends(get_db)):
    _set(db, "security_session_timeout_minutes",  str(config.session_timeout_minutes))
    _set(db, "security_lockout_threshold",        str(config.lockout_threshold))
    _set(db, "security_lockout_duration_minutes", str(config.lockout_duration_minutes))
    _set(db, "security_lockout_reset_minutes",    str(config.lockout_reset_minutes))
    db.commit()
    return {"message": "Security settings saved"}
