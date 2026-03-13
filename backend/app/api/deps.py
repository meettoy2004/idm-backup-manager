import logging
import redis as _redis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from ..config.database import get_db
from ..models.user import User
from ..config import settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)

def _is_token_denylisted(raw_token: str) -> bool:
    """Check Redis denylist for logged-out tokens. Returns False on Redis errors."""
    try:
        r = _redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=1)
        return r.exists(f"denylist:{raw_token}") > 0
    except Exception as exc:
        logger.warning("Redis denylist check failed (allowing request): %s", exc)
        return False

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    raw_token = credentials.credentials

    if _is_token_denylisted(raw_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

def require_editor(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access or above required. Viewer accounts are read-only.")
    return current_user

def require_viewer(current_user: User = Depends(get_current_user)) -> User:
    return current_user
