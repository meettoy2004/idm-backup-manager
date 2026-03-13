from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.restore_operation import RestoreOperation
from ...models.server import Server
from ...models.backup_job import BackupJob
from ...models.user import User
from ...services.restore_service import RestoreService
from ...services.audit_service import log_action, AuditAction
from ...api.deps import get_current_user, require_admin, require_editor
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class RestoreCreate(BaseModel):
    job_id: Optional[int] = None
    server_id: int
    restore_path: Optional[str] = "/var/lib/ipa/restore"
    gpg_passphrase: str

class RestoreResponse(BaseModel):
    id: int
    job_id: Optional[int] = None
    server_id: Optional[int] = None
    requested_by: Optional[int] = None
    restore_status: str
    restore_path: Optional[str] = None
    gpg_decrypt_output: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

@router.get("", response_model=List[RestoreResponse])
@router.get("/", response_model=List[RestoreResponse])
def list_restores(server_id: Optional[int] = None, limit: int = 50, offset: int = 0,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    limit = max(1, min(limit, 500))
    query = db.query(RestoreOperation).order_by(RestoreOperation.created_at.desc())
    if server_id:
        query = query.filter(RestoreOperation.server_id == server_id)
    return query.offset(offset).limit(limit).all()

@router.get("/{restore_id}", response_model=RestoreResponse)
@router.get("/{restore_id}/", response_model=RestoreResponse)
def get_restore(restore_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    r = db.query(RestoreOperation).filter(RestoreOperation.id == restore_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restore operation not found")
    return r

@router.post("", response_model=RestoreResponse)
@router.post("/", response_model=RestoreResponse)
def create_restore(body: RestoreCreate, request: Request,
                   background_tasks: BackgroundTasks, db: Session = Depends(get_db),
                   current_user: User = Depends(require_editor)):
    server = db.query(Server).filter(Server.id == body.server_id).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    if body.job_id:
        job = db.query(BackupJob).filter(BackupJob.id == body.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Backup job not found")

    restore_op = RestoreOperation(
        job_id=body.job_id,
        server_id=body.server_id,
        restore_path=body.restore_path,
        restore_status="pending",
        requested_by=current_user.id,
    )
    db.add(restore_op)
    db.commit()
    db.refresh(restore_op)

    passphrase = body.gpg_passphrase

    def run_restore():
        from ...config.database import SessionLocal
        _db = SessionLocal()
        try:
            op = _db.query(RestoreOperation).filter(RestoreOperation.id == restore_op.id).first()
            svc = RestoreService()
            svc.start_restore(op, _db, passphrase)
        finally:
            _db.close()

    background_tasks.add_task(run_restore)

    log_action(db, "RESTORE_TRIGGERED", user=current_user.email,
        resource="restore_operations",
        resource_id=restore_op.id,
        detail=f"Restore triggered on server '{server.name}' for job {body.job_id}",
        ip_address=request.client.host)

    return restore_op

@router.delete("/{restore_id}")
@router.delete("/{restore_id}/")
def cancel_restore(restore_id: int, request: Request, db: Session = Depends(get_db),
                   current_user: User = Depends(require_editor)):
    r = db.query(RestoreOperation).filter(RestoreOperation.id == restore_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Restore operation not found")
    if r.restore_status not in ("pending",):
        raise HTTPException(status_code=400, detail=f"Cannot cancel a restore in '{r.restore_status}' state")
    r.restore_status = "cancelled"
    db.commit()
    log_action(db, AuditAction.RESTORE_CANCELLED, user=current_user.email,
        resource="restore_operations", resource_id=restore_id,
        detail=f"Restore operation {restore_id} cancelled",
        ip_address=request.client.host)
    return {"message": "Restore cancelled"}
