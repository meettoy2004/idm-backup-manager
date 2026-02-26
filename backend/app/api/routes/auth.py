from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta
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


def _get_security(db: Session) -> dict:
    """Read security policy settings from system_settings, falling back to safe defaults."""
    from ...models.system_setting import SystemSetting
    def g(key, default):
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        return int(row.value) if (row and row.value) else default
    return {
        "session_timeout_minutes":  g("security_session_timeout_minutes",  60),
        "lockout_threshold":        g("security_lockout_threshold",          5),
        "lockout_duration_minutes": g("security_lockout_duration_minutes",  15),
        "lockout_reset_minutes":    g("security_lockout_reset_minutes",     10),
    }

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
    ip = request.client.host if request else None
    now = datetime.now(timezone.utc)
    sec = _get_security(db)

    user = db.query(User).filter(
        (User.username == form_data.username) | (User.email == form_data.username),
        User.auth_method == "local",
        User.is_active == True
    ).first()

    # ── Lockout check ─────────────────────────────────────────────────────────
    if user and user.locked_until:
        if user.locked_until > now:
            remaining = int((user.locked_until - now).total_seconds() / 60) + 1
            log_action(db, "LOGIN_FAILED", user=form_data.username,
                detail=f"Login blocked — account locked for {remaining} more minute(s)",
                ip_address=ip, status="failure")
            raise HTTPException(status_code=423,
                detail=f"Account locked. Try again in {remaining} minute(s).")
        else:
            # Lockout window expired — automatically unlock
            user.failed_logins  = 0
            user.locked_until   = None
            user.last_failed_at = None
            db.commit()

    # ── Credential check ──────────────────────────────────────────────────────
    if not user or not verify_password(form_data.password, user.hashed_password):
        if user:
            # Reset failure counter if enough idle time has passed
            if (user.last_failed_at and
                    (now - user.last_failed_at).total_seconds() > sec["lockout_reset_minutes"] * 60):
                user.failed_logins = 0

            user.failed_logins  = (user.failed_logins or 0) + 1
            user.last_failed_at = now

            if user.failed_logins >= sec["lockout_threshold"]:
                user.locked_until   = now + timedelta(minutes=sec["lockout_duration_minutes"])
                user.failed_logins  = 0
                user.last_failed_at = None
                db.commit()
                log_action(db, "ACCOUNT_LOCKED", user=form_data.username,
                    detail=f"Account locked after {sec['lockout_threshold']} failed attempts",
                    ip_address=ip, status="failure")
                raise HTTPException(status_code=423,
                    detail=f"Too many failed attempts. Account locked for {sec['lockout_duration_minutes']} minute(s).")
            db.commit()

        log_action(db, "LOGIN_FAILED", user=form_data.username,
            detail=f"Failed login for '{form_data.username}'",
            ip_address=ip, status="failure")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # ── Successful login ──────────────────────────────────────────────────────
    # Reset any leftover lockout state
    user.failed_logins  = 0
    user.locked_until   = None
    user.last_failed_at = None

    # Check if password change is required
    if user.requires_password_change:
        temp_token = create_access_token(
            data={"sub": str(user.id), "role": user.role, "requires_password_change": True}
        )
        db.commit()
        log_action(db, "LOGIN_REQUIRES_PASSWORD_CHANGE", user=user.email,
            detail=f"Login for '{user.username}' requires password change",
            ip_address=ip)
        return {
            "requires_password_change": True,
            "temp_token": temp_token,
            "message": "Password change required before login"
        }

    # Issue token using the configured session timeout
    expires = timedelta(minutes=sec["session_timeout_minutes"])
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role},
        expires_delta=expires,
    )
    user.last_login = now
    db.commit()

    log_action(db, "LOGIN_SUCCESS", user=user.email,
        detail=f"Successful login for '{user.username}'",
        ip_address=ip)

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
