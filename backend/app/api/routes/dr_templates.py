from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict
from ...config.database import get_db
from ...models.dr_template import DRTemplate
from ...services.audit_service import log_action, AuditAction
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class DRTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    organization_id: Optional[int] = None
    template_config: Optional[Dict[str, Any]] = None

class DRTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    organization_id: Optional[int] = None
    template_config: Optional[Dict[str, Any]] = None
    is_active: bool
    created_by: Optional[int] = None
    created_at: datetime
    class Config:
        from_attributes = True

@router.get("", response_model=List[DRTemplateResponse])
@router.get("/", response_model=List[DRTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(DRTemplate).filter(DRTemplate.is_active == True).all()

@router.post("", response_model=DRTemplateResponse)
@router.post("/", response_model=DRTemplateResponse)
def create_template(body: DRTemplateCreate, request: Request, db: Session = Depends(get_db)):
    t = DRTemplate(**body.dict())
    db.add(t)
    db.commit()
    db.refresh(t)
    log_action(db, AuditAction.SERVER_CREATED, resource="dr_templates",
        resource_id=t.id, detail=f"Created DR template '{t.name}'",
        ip_address=request.client.host)
    return t

@router.get("/{template_id}", response_model=DRTemplateResponse)
@router.get("/{template_id}/", response_model=DRTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(DRTemplate).filter(DRTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="DR template not found")
    return t

@router.put("/{template_id}", response_model=DRTemplateResponse)
@router.put("/{template_id}/", response_model=DRTemplateResponse)
def update_template(template_id: int, updates: dict, db: Session = Depends(get_db)):
    t = db.query(DRTemplate).filter(DRTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="DR template not found")
    for field in ("name", "description", "template_config", "is_active", "organization_id"):
        if field in updates:
            setattr(t, field, updates[field])
    db.commit()
    db.refresh(t)
    return t

@router.delete("/{template_id}")
@router.delete("/{template_id}/")
def delete_template(template_id: int, request: Request, db: Session = Depends(get_db)):
    t = db.query(DRTemplate).filter(DRTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="DR template not found")
    name = t.name
    t.is_active = False
    db.commit()
    log_action(db, AuditAction.SERVER_DELETED, resource="dr_templates",
        resource_id=template_id, detail=f"Deactivated DR template '{name}'",
        ip_address=request.client.host)
    return {"message": f"DR template '{name}' deactivated"}
