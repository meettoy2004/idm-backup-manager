from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt, JWTError
from ...config.database import get_db
from ...config import settings
from ...models.user import User
from ...services.auth_service import hash_password, verify_password, create_access_token
from ...services.audit_service import log_action
from ...api.deps import get_current_user

router = APIRouter()

class SetPasswordRequest(BaseModel):
    token: str
    new_password: str

class ForceChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/complete-password-change")
@router.post("/complete-password-change/")
def complete_password_change(
    body: SetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Complete forced password change on first login.
    Token must have 'requires_password_change' claim.
    """
    try:
        payload = jwt.decode(body.token, settings.SECRET_KEY, algorithms=["HS256"])
        
        if not payload.get("requires_password_change"):
            raise HTTPException(status_code=400, detail="Invalid token - not a password change token")
        
        user_id = int(payload.get("sub"))
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.requires_password_change:
            raise HTTPException(status_code=400, detail="Password change not required")
        
        # Validate new password
        if len(body.new_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
        
        # Set new password and clear flag
        user.hashed_password = hash_password(body.new_password)
        user.requires_password_change = False
        db.commit()
        
        log_action(
            db, "PASSWORD_CHANGED", user=user.email,
            detail=f"User '{user.username}' completed required password change",
            ip_address=request.client.host
        )
        
        # Return normal login token
        access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
        user.last_login = func.now()
        db.commit()
        
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

@router.post("/force-password-change")
@router.post("/force-password-change/")
def force_password_change_self(
    body: ForceChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    User is logged in but requires_password_change is True.
    They must verify current password and set a new one.
    """
    if current_user.auth_method != "local":
        raise HTTPException(status_code=400, detail="SSO users cannot change password here")
    
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    current_user.hashed_password = hash_password(body.new_password)
    current_user.requires_password_change = False
    db.commit()
    
    log_action(
        db, "PASSWORD_CHANGED", user=current_user.email,
        detail=f"User '{current_user.username}' changed password (forced)",
        ip_address=request.client.host
    )
    
    return {"message": "Password changed successfully"}
