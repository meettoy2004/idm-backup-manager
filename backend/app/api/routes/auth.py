from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
from ...config.database import get_db
from ...config import settings
from ...models.user import User
from ...services.auth_service import (
    verify_password, hash_password, create_access_token, create_admin_user
)
from ...services.audit_service import log_action
from ...api.deps import get_current_user, require_admin
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    role: str
    auth_method: str
    is_active: bool
    requires_password_change: bool
    last_login: Optional[datetime]
    created_at: datetime
    class Config:
        from_attributes = True

class UserCreate(BaseModel):
    email: str
    username: str
    full_name: Optional[str] = None
    password: str
    role: str = "viewer"
    requires_password_change: bool = False

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    requires_password_change: Optional[bool] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class CompletePasswordChangeRequest(BaseModel):
    token: str
    new_password: str

# ── Login ──────────────────────────────────────────────────────────────────

@router.post("/login")
@router.post("/login/")
@limiter.limit("10/minute")
def login(form_data: OAuth2PasswordRequestForm = Depends(),
          request: Request = None, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username),
        User.auth_method == "local",
        User.is_active == True
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        log_action(db, "LOGIN_FAILED", user=form_data.username,
            detail=f"Failed login for '{form_data.username}'",
            ip_address=request.client.host if request else None, status="failure")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if password change is required
    if user.requires_password_change:
        temp_token = create_access_token(
            data={"sub": str(user.id), "role": user.role, "requires_password_change": True}
        )
        log_action(db, "LOGIN_REQUIRES_PASSWORD_CHANGE", user=user.email,
            detail=f"Login for '{user.username}' requires password change",
            ip_address=request.client.host if request else None)
        return {
            "requires_password_change": True,
            "temp_token": temp_token,
            "message": "Password change required before login"
        }

    # Normal login flow
    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    log_action(db, "LOGIN_SUCCESS", user=user.email,
        detail=f"Successful login for '{user.username}'",
        ip_address=request.client.host if request else None)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "auth_method": user.auth_method,
        }
    }

@router.post("/logout")
@router.post("/logout/")
def logout(request: Request, current_user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    log_action(db, "LOGOUT", user=current_user.email,
        detail=f"User '{current_user.username}' logged out",
        ip_address=request.client.host)
    return {"message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
@router.get("/me/", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# ── Password Change ────────────────────────────────────────────────────────

@router.post("/complete-password-change")
@router.post("/complete-password-change/")
def complete_password_change(
    body: CompletePasswordChangeRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """Complete forced password change on first login"""
    from jose import jwt, JWTError
    
    try:
        payload = jwt.decode(body.token, settings.SECRET_KEY, algorithms=["HS256"])
        
        if not payload.get("requires_password_change"):
            raise HTTPException(status_code=400, detail="Invalid token")
        
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.requires_password_change:
            raise HTTPException(status_code=400, detail="Password change not required")
        
        if len(body.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        user.hashed_password = hash_password(body.new_password)
        user.requires_password_change = False
        user.last_login = datetime.now(timezone.utc)
        db.commit()
        
        log_action(db, "PASSWORD_CHANGED", user=user.email,
            detail=f"User '{user.username}' completed required password change",
            ip_address=request.client.host)
        
        access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "auth_method": user.auth_method,
            }
        }
        
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@router.post("/change-password")
@router.post("/change-password/")
def change_own_password(
    body: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.auth_method != "local":
        raise HTTPException(status_code=400, detail="SSO users cannot change password here")
    
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    current_user.hashed_password = hash_password(body.new_password)
    current_user.requires_password_change = False
    db.commit()
    
    log_action(db, "PASSWORD_CHANGED", user=current_user.email,
        detail=f"User '{current_user.username}' changed their password",
        ip_address=request.client.host)
    
    return {"message": "Password changed successfully"}

# ── User Management (admin only) ───────────────────────────────────────────

@router.get("/users", response_model=List[UserResponse])
@router.get("/users/", response_model=List[UserResponse])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(User).order_by(User.created_at.desc()).all()

@router.post("/users", response_model=UserResponse)
@router.post("/users/", response_model=UserResponse)
def create_user(body: UserCreate, request: Request,
                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already exists")
    
    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        hashed_password=hash_password(body.password) if body.password else None,
        role=body.role,
        auth_method="local",
        is_active=True,
        requires_password_change=body.requires_password_change
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    log_action(db, "USER_CREATED", user=admin.email,
        detail=f"Admin created user '{body.username}' ({body.email}) role={body.role} requires_pwd_change={body.requires_password_change}",
        ip_address=request.client.host)
    
    return user

@router.patch("/users/{user_id}", response_model=UserResponse)
@router.patch("/users/{user_id}/", response_model=UserResponse)
def update_user(user_id: int, body: UserUpdate, request: Request,
                db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.requires_password_change is not None:
        user.requires_password_change = body.requires_password_change
    if body.password:
        user.hashed_password = hash_password(body.password)
    
    db.commit()
    db.refresh(user)
    
    log_action(db, "USER_UPDATED", user=admin.email,
        detail=f"Updated user id={user_id}", ip_address=request.client.host)
    
    return user

@router.post("/bootstrap")
@router.post("/bootstrap/")
def bootstrap_admin(db: Session = Depends(get_db)):
    """Create first admin if no users exist"""
    if db.query(User).count() > 0:
        raise HTTPException(status_code=400, detail="Users already exist")
    
    user = create_admin_user(
        db,
        email=getattr(settings, "BOOTSTRAP_ADMIN_EMAIL", "admin@local"),
        username="admin",
        password=getattr(settings, "BOOTSTRAP_ADMIN_PASSWORD", "changeme123"),
        full_name="System Administrator"
    )
    return {"message": f"Admin created: {user.email}", "username": user.username}
