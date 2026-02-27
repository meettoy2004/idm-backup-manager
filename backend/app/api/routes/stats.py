from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from ...config.database import get_db
from ...models.server import Server
from ...models.backup_config import BackupConfig

router = APIRouter()

@router.get("/overview")
@router.get("/overview/")
def get_overview(db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=30)

    total_servers   = db.execute(text("SELECT COUNT(*) FROM servers")).scalar()
    active_servers  = db.execute(text("SELECT COUNT(*) FROM servers WHERE is_active = true")).scalar()
    total_configs   = db.execute(text("SELECT COUNT(*) FROM backup_configs")).scalar()
    enabled_configs = db.execute(text("SELECT COUNT(*) FROM backup_configs WHERE is_enabled = true")).scalar()
    total_jobs      = db.execute(text("SELECT COUNT(*) FROM backup_jobs WHERE created_at >= :s"), {"s": since}).scalar()
    success_jobs    = db.execute(text("SELECT COUNT(*) FROM backup_jobs WHERE created_at >= :s AND LOWER(CAST(status AS TEXT)) = 'success'"), {"s": since}).scalar()
    failed_jobs     = db.execute(text("SELECT COUNT(*) FROM backup_jobs WHERE created_at >= :s AND LOWER(CAST(status AS TEXT)) = 'failed'"),  {"s": since}).scalar()
    success_rate    = round((success_jobs / total_jobs * 100), 1) if total_jobs > 0 else 0

    rows = db.execute(text("""
        SELECT s.id, s.name, s.hostname, s.is_active,
               j.status, j.created_at, j.error_message
        FROM servers s
        LEFT JOIN LATERAL (
            SELECT status, created_at, error_message
            FROM backup_jobs
            WHERE server_id = s.id
            ORDER BY created_at DESC LIMIT 1
        ) j ON true
        ORDER BY s.name
    """)).fetchall()

    server_health = [{
        "server_id":       r[0],
        "server_name":     r[1],
        "hostname":        r[2],
        "is_active":       r[3],
        "last_job_status": r[4].lower() if r[4] else "never",
        "last_job_time":   r[5].isoformat() if r[5] else None,
        "last_job_error":  r[6],
    } for r in rows]

    return {
        "servers":       {"total": total_servers,  "active": active_servers},
        "configs":       {"total": total_configs,   "enabled": enabled_configs},
        "jobs_30d":      {"total": total_jobs, "success": success_jobs, "failed": failed_jobs, "success_rate": success_rate},
        "server_health": server_health
    }

@router.get("/jobs-over-time")
@router.get("/jobs-over-time/")
def get_jobs_over_time(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows  = db.execute(text("""
        SELECT DATE(created_at) as day,
               COUNT(*) as total,
               SUM(CASE WHEN LOWER(CAST(status AS TEXT)) = 'success' THEN 1 ELSE 0 END) as success,
               SUM(CASE WHEN LOWER(CAST(status AS TEXT)) = 'failed'  THEN 1 ELSE 0 END) as failed
        FROM backup_jobs WHERE created_at >= :s
        GROUP BY DATE(created_at) ORDER BY day
    """), {"s": since}).fetchall()

    daily = {str(r[0]): {"date": str(r[0]), "total": int(r[1]), "success": int(r[2]), "failed": int(r[3])} for r in rows}
    result = []
    for i in range(days):
        day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        result.append(daily.get(day, {"date": day, "success": 0, "failed": 0, "total": 0}))
    return result

@router.get("/success-rate-by-server")
@router.get("/success-rate-by-server/")
def get_success_rate_by_server(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows  = db.execute(text("""
        SELECT s.name, s.hostname,
               COUNT(j.id) as total,
               SUM(CASE WHEN CAST(j.status AS TEXT) = 'success' THEN 1 ELSE 0 END) as success,
               SUM(CASE WHEN CAST(j.status AS TEXT) = 'failed'  THEN 1 ELSE 0 END) as failed
        FROM servers s
        LEFT JOIN backup_jobs j ON j.server_id = s.id AND j.created_at >= :s
        GROUP BY s.id, s.name, s.hostname ORDER BY s.name
    """), {"s": since}).fetchall()

    return [{
        "server_name":  r[0],
        "hostname":     r[1],
        "total_jobs":   int(r[2] or 0),
        "success":      int(r[3] or 0),
        "failed":       int(r[4] or 0),
        "success_rate": round((int(r[3] or 0) / int(r[2]) * 100), 1) if r[2] and int(r[2]) > 0 else 0
    } for r in rows]

@router.get("/recent-failures")
@router.get("/recent-failures/")
def get_recent_failures(limit: int = 10, db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT j.id, j.error_message, j.created_at, j.started_at, j.completed_at,
               s.name, s.hostname
        FROM backup_jobs j
        LEFT JOIN servers s ON s.id = j.server_id
        WHERE CAST(j.status AS TEXT) = 'failed'
        ORDER BY j.created_at DESC LIMIT :lim
    """), {"lim": limit}).fetchall()

    return [{
        "job_id":        r[0],
        "error_message": r[1],
        "created_at":    r[2].isoformat() if r[2] else None,
        "started_at":    r[3].isoformat() if r[3] else None,
        "completed_at":  r[4].isoformat() if r[4] else None,
        "server_name":   r[5] or "Unknown",
        "hostname":      r[6] or "Unknown",
    } for r in rows]

@router.get("/job-duration-stats")
@router.get("/job-duration-stats/")
def get_job_duration_stats(days: int = 30, db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows  = db.execute(text("""
        SELECT s.name,
               AVG(EXTRACT(EPOCH FROM (j.completed_at - j.started_at))) as avg_dur,
               MIN(EXTRACT(EPOCH FROM (j.completed_at - j.started_at))) as min_dur,
               MAX(EXTRACT(EPOCH FROM (j.completed_at - j.started_at))) as max_dur,
               COUNT(*) as cnt
        FROM backup_jobs j
        JOIN servers s ON s.id = j.server_id
        WHERE CAST(j.status AS TEXT) = 'success'
          AND j.created_at >= :s
          AND j.started_at IS NOT NULL
          AND j.completed_at IS NOT NULL
        GROUP BY s.id, s.name ORDER BY s.name
    """), {"s": since}).fetchall()

    return [{
        "server_name":          r[0],
        "avg_duration_seconds": round(float(r[1])) if r[1] else 0,
        "min_duration_seconds": round(float(r[2])) if r[2] else 0,
        "max_duration_seconds": round(float(r[3])) if r[3] else 0,
        "job_count":            int(r[4])
    } for r in rows]
