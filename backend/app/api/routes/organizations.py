from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from ...config.database import get_db
from ...models.organization import Organization, UserOrganization
from ...services.audit_service import log_action, AuditAction
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class OrgCreate(BaseModel):
    name: str
    description: Optional[str] = None

class OrgResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

class MemberAdd(BaseModel):
    user_id: int
    role: str = "member"

@router.get("", response_model=List[OrgResponse])
@router.get("/", response_model=List[OrgResponse])
def list_orgs(db: Session = Depends(get_db)):
    return db.query(Organization).filter(Organization.is_active == True).all()

@router.post("", response_model=OrgResponse)
@router.post("/", response_model=OrgResponse)
def create_org(org: OrgCreate, request: Request, db: Session = Depends(get_db)):
    existing = db.query(Organization).filter(Organization.name == org.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization name already exists")
    db_org = Organization(**org.dict())
    db.add(db_org)
    db.commit()
    db.refresh(db_org)
    log_action(db, AuditAction.SERVER_CREATED, resource="organizations",
        resource_id=db_org.id, detail=f"Created organization '{db_org.name}'",
        ip_address=request.client.host)
    return db_org

@router.get("/{org_id}", response_model=OrgResponse)
@router.get("/{org_id}/", response_model=OrgResponse)
def get_org(org_id: int, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.put("/{org_id}", response_model=OrgResponse)
@router.put("/{org_id}/", response_model=OrgResponse)
def update_org(org_id: int, updates: dict, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field in ("name", "description", "is_active"):
        if field in updates:
            setattr(org, field, updates[field])
    db.commit()
    db.refresh(org)
    return org

@router.delete("/{org_id}")
@router.delete("/{org_id}/")
def delete_org(org_id: int, request: Request, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    name = org.name
    org.is_active = False
    db.commit()
    log_action(db, AuditAction.SERVER_DELETED, resource="organizations",
        resource_id=org_id, detail=f"Deactivated organization '{name}'",
        ip_address=request.client.host)
    return {"message": f"Organization '{name}' deactivated"}

@router.post("/{org_id}/members")
@router.post("/{org_id}/members/")
def add_member(org_id: int, body: MemberAdd, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    existing = db.query(UserOrganization).filter(
        UserOrganization.organization_id == org_id,
        UserOrganization.user_id == body.user_id
    ).first()
    if existing:
        existing.role = body.role
    else:
        db.add(UserOrganization(user_id=body.user_id, organization_id=org_id, role=body.role))
    db.commit()
    return {"message": "Member added"}

@router.delete("/{org_id}/members/{user_id}")
@router.delete("/{org_id}/members/{user_id}/")
def remove_member(org_id: int, user_id: int, db: Session = Depends(get_db)):
    member = db.query(UserOrganization).filter(
        UserOrganization.organization_id == org_id,
        UserOrganization.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    db.delete(member)
    db.commit()
    return {"message": "Member removed"}
