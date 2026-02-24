from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import JWTError, jwt, exceptions
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from ..models.user import User
from ..config import settings
import logging

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = settings.SECRET_KEY
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60   # 1 hour

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Token created for sub={data.get('sub')} expires={expire}")
    return encoded

def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Token decoded OK: sub={payload.get('sub')}")
        return payload
    except exceptions.ExpiredSignatureError:
        logger.warning("Token decode failed: expired")
        return None
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        return None

def authenticate_local(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(
        (User.username == username) | (User.email == username),
        User.auth_method == "local",
        User.is_active == True
    ).first()
    if not user or not user.hashed_password:
        return None
    if not verify_password(password[:72], user.hashed_password):
        return None
    return user

def get_or_create_oidc_user(db: Session, claims: dict) -> User:
    sub   = claims.get("sub")
    email = claims.get("email", "")
    name  = claims.get("name", email)

    user = db.query(User).filter(User.oidc_subject == sub).first()
    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oidc_subject = sub
            user.auth_method  = "oidc"
        else:
            username = email.split("@")[0]
            base, counter = username, 1
            while db.query(User).filter(User.username == username).first():
                username = f"{base}{counter}"
                counter += 1
            user = User(
                email=email, username=username, full_name=name,
                auth_method="oidc", oidc_subject=sub,
                role="viewer", is_active=True
            )
            db.add(user)
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user

def create_admin_user(db: Session, email: str, username: str, password: str, full_name: str = ""):
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    user = User(
        email=email, username=username, full_name=full_name,
        hashed_password=hash_password(password),
        role="admin", auth_method="local", is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
