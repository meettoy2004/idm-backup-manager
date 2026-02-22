from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timedelta
from ...config.database import get_db
from ...models.audit_log import AuditLog
from pydantic import BaseModel
import csv, io

router = APIRouter()

class AuditLogResponse(BaseModel):
    id:          int
    timestamp:   datetime
    user:        str
    auth_method: Optional[str]
    action:      str
    resource:    Optional[str]
    resource_id: Optional[str]
    detail:      Optional[str]
    ip_address:  Optional[str]
    status:      str
    class Config:
        from_attributes = True

@router.get("")
@router.get("/")
def list_audit_logs(
    page:       int = 1,
    per_page:   int = 50,
    action:     Optional[str] = None,
    user:       Optional[str] = None,
    resource:   Optional[str] = None,
    status:     Optional[str] = None,
    days:       Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())

    if action:   query = query.filter(AuditLog.action == action)
    if user:     query = query.filter(AuditLog.user.ilike(f"%{user}%"))
    if resource: query = query.filter(AuditLog.resource == resource)
    if status:   query = query.filter(AuditLog.status == status)
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        query = query.filter(AuditLog.timestamp >= since)

    total  = query.count()
    offset = (page - 1) * per_page
    logs   = query.offset(offset).limit(per_page).all()

    return {
        "total":    total,
        "page":     page,
        "per_page": per_page,
        "pages":    (total + per_page - 1) // per_page,
        "logs":     [AuditLogResponse.model_validate(l) for l in logs]
    }

@router.get("/summary")
@router.get("/summary/")
def get_audit_summary(days: int = 7, db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(days=days)
    rows  = db.execute(text("""
        SELECT action, COUNT(*) as count
        FROM audit_logs WHERE timestamp >= :s
        GROUP BY action ORDER BY count DESC
    """), {"s": since}).fetchall()

    users = db.execute(text("""
        SELECT "user", COUNT(*) as count
        FROM audit_logs WHERE timestamp >= :s
        GROUP BY "user" ORDER BY count DESC LIMIT 10
    """), {"s": since}).fetchall()

    return {
        "by_action": [{"action": r[0], "count": int(r[1])} for r in rows],
        "by_user":   [{"user": r[0],   "count": int(r[1])} for r in users],
        "total":     sum(r[1] for r in rows)
    }

@router.get("/export")
def export_audit_logs(
    days: int = 30,
    db: Session = Depends(get_db)
):
    since = datetime.utcnow() - timedelta(days=days)
    logs  = db.query(AuditLog).filter(
        AuditLog.timestamp >= since
    ).order_by(AuditLog.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp","user","auth_method","action","resource","resource_id","detail","ip_address","status"])
    for l in logs:
        writer.writerow([l.timestamp, l.user, l.auth_method, l.action, l.resource, l.resource_id, l.detail, l.ip_address, l.status])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit_log_{datetime.utcnow().strftime('%Y%m%d')}.csv"}
    )
