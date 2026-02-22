from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.verification_log import VerificationLog
from ...models.backup_job import BackupJob
from ...services.verification_service import VerificationService
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class VerificationResponse(BaseModel):
    id: int
    job_id: int
    verification_status: str
    gpg_verify_output: Optional[str] = None
    integrity_check_passed: Optional[bool] = None
    verified_at: datetime
    error_message: Optional[str] = None
    class Config:
        from_attributes = True

@router.get("", response_model=List[VerificationResponse])
@router.get("/", response_model=List[VerificationResponse])
def list_verifications(job_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(VerificationLog).order_by(VerificationLog.verified_at.desc())
    if job_id:
        query = query.filter(VerificationLog.job_id == job_id)
    return query.limit(100).all()

@router.get("/{verification_id}", response_model=VerificationResponse)
@router.get("/{verification_id}/", response_model=VerificationResponse)
def get_verification(verification_id: int, db: Session = Depends(get_db)):
    v = db.query(VerificationLog).filter(VerificationLog.id == verification_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Verification log not found")
    return v

@router.post("/trigger/{job_id}")
@router.post("/trigger/{job_id}/")
def trigger_verification(job_id: int, background_tasks: BackgroundTasks,
                          db: Session = Depends(get_db)):
    job = db.query(BackupJob).filter(BackupJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "SUCCESS":
        raise HTTPException(status_code=400, detail="Can only verify successful jobs")

    def run_verification():
        from ...config.database import SessionLocal
        _db = SessionLocal()
        try:
            svc = VerificationService()
            svc.verify_job(job, _db)
        finally:
            _db.close()

    background_tasks.add_task(run_verification)
    return {"message": f"Verification triggered for job {job_id}"}
