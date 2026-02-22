from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.backup_job import BackupJob
from ...models.server import Server
from ...services.ssh_service import SSHService
from ...services.audit_service import log_action, AuditAction
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class JobResponse(BaseModel):
    id:            int
    server_id:     int
    config_id:     Optional[int]
    status:        str
    started_at:    Optional[datetime]
    completed_at:  Optional[datetime]
    log_output:    Optional[str]
    error_message: Optional[str]
    created_at:    datetime
    class Config:
        from_attributes = True

class TriggerRequest(BaseModel):
    server_id: int

@router.get("", response_model=List[JobResponse])
@router.get("/", response_model=List[JobResponse])
def list_jobs(server_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(BackupJob).order_by(BackupJob.created_at.desc())
    if server_id: query = query.filter(BackupJob.server_id == server_id)
    if status:    query = query.filter(BackupJob.status == status.lower())
    return query.limit(50).all()

@router.get("/server/{server_id}/latest", response_model=JobResponse)
def get_latest_job(server_id: int, db: Session = Depends(get_db)):
    job = db.query(BackupJob).filter(BackupJob.server_id == server_id).order_by(BackupJob.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No jobs found")
    return job

@router.get("/{job_id}", response_model=JobResponse)
@router.get("/{job_id}/", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(BackupJob).filter(BackupJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.post("/trigger")
@router.post("/trigger/")
def trigger_backup(request: Request, body: TriggerRequest, db: Session = Depends(get_db)):
    server = db.query(Server).filter(Server.id == body.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    job = BackupJob(server_id=server.id, status="running", started_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)

    log_action(db, AuditAction.JOB_TRIGGERED, resource="jobs",
        resource_id=job.id,
        detail=f"Manual backup triggered for '{server.name}' ({server.hostname})",
        ip_address=request.client.host)

    ssh_service = SSHService()
    try:
        client = ssh_service.connect(server.hostname, server.port, server.username)
        exit_code, output, error = ssh_service.execute_command(client, "systemctl start ipa-backup.service", sudo=True)
        client.close()
        if exit_code == 0:
            job.status = "success"
            job.log_output = output
            log_action(db, AuditAction.JOB_COMPLETED, resource="jobs", resource_id=job.id,
                detail=f"Backup completed successfully on '{server.name}'")
        else:
            job.status = "failed"
            job.error_message = f"Failed: {error}"
            log_action(db, AuditAction.JOB_FAILED, resource="jobs", resource_id=job.id,
                detail=f"Backup failed on '{server.name}': {error}", status="failure")
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        log_action(db, AuditAction.JOB_FAILED, resource="jobs", resource_id=job.id,
            detail=f"Backup failed on '{server.name}': {e}", status="failure")

    job.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job

@router.delete("/{job_id}")
@router.delete("/{job_id}/")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    """Delete a backup job (admin only)"""
    job = db.query(BackupJob).filter(BackupJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.delete(job)
    db.commit()
    return {"message": "Job deleted"}
