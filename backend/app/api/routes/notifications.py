from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.notification_setting import NotificationSetting
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class NotificationCreate(BaseModel):
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    notify_on_failure: bool = True
    notify_on_success: bool = False
    notify_threshold: int = 3
    email_addresses: Optional[List[str]] = None
    slack_webhook_url: Optional[str] = None
    is_enabled: bool = True

class NotificationResponse(BaseModel):
    id: int
    organization_id: Optional[int] = None
    user_id: Optional[int] = None
    notify_on_failure: bool
    notify_on_success: bool
    notify_threshold: int
    email_addresses: Optional[List[str]] = None
    slack_webhook_url: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    class Config:
        from_attributes = True

@router.get("", response_model=List[NotificationResponse])
@router.get("/", response_model=List[NotificationResponse])
def list_notification_settings(
    user_id: Optional[int] = None,
    org_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(NotificationSetting)
    if user_id:
        query = query.filter(NotificationSetting.user_id == user_id)
    if org_id:
        query = query.filter(NotificationSetting.organization_id == org_id)
    return query.all()

@router.post("", response_model=NotificationResponse)
@router.post("/", response_model=NotificationResponse)
def create_notification_setting(body: NotificationCreate, db: Session = Depends(get_db)):
    ns = NotificationSetting(**body.dict())
    db.add(ns)
    db.commit()
    db.refresh(ns)
    return ns

@router.get("/{ns_id}", response_model=NotificationResponse)
@router.get("/{ns_id}/", response_model=NotificationResponse)
def get_notification_setting(ns_id: int, db: Session = Depends(get_db)):
    ns = db.query(NotificationSetting).filter(NotificationSetting.id == ns_id).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Notification setting not found")
    return ns

@router.put("/{ns_id}", response_model=NotificationResponse)
@router.put("/{ns_id}/", response_model=NotificationResponse)
def update_notification_setting(ns_id: int, updates: dict, db: Session = Depends(get_db)):
    ns = db.query(NotificationSetting).filter(NotificationSetting.id == ns_id).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Notification setting not found")
    for field in ("notify_on_failure", "notify_on_success", "notify_threshold",
                  "email_addresses", "slack_webhook_url", "is_enabled"):
        if field in updates:
            setattr(ns, field, updates[field])
    db.commit()
    db.refresh(ns)
    return ns

@router.delete("/{ns_id}")
@router.delete("/{ns_id}/")
def delete_notification_setting(ns_id: int, db: Session = Depends(get_db)):
    ns = db.query(NotificationSetting).filter(NotificationSetting.id == ns_id).first()
    if not ns:
        raise HTTPException(status_code=404, detail="Notification setting not found")
    db.delete(ns)
    db.commit()
    return {"message": "Notification setting deleted"}
