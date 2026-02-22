from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ...config.database import get_db
from ...services.report_service import ReportService

router = APIRouter()

@router.get("/weekly")
@router.get("/weekly/")
def get_weekly_report(db: Session = Depends(get_db)):
    svc = ReportService(db)
    return svc.generate_weekly_report()

@router.get("/monthly")
@router.get("/monthly/")
def get_monthly_report(db: Session = Depends(get_db)):
    svc = ReportService(db)
    return svc.generate_monthly_report()
