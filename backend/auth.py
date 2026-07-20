"""Authentication: password hashing, JWT, and role-based access (Phase 9).

Administrators log in and receive a JWT; protected routes require it. Patients
use guest access (no auth) — decided for this prototype.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.db import get_db
from backend.db_models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/admin/login", auto_error=True)


def hash_password(password: str) -> str:
    # bcrypt operates on <=72 bytes; truncate defensively (avoids passlib's
    # incompatibility with bcrypt 4.x).
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user and user.active and verify_password(password, user.password_hash):
        return user
    return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    creds_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token",
                             {"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        username = payload.get("sub")
        if not username:
            raise creds_exc
    except JWTError:
        raise creds_exc
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.active:
        raise creds_exc
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("administrator", "roster_manager", "emergency_officer", "inventory_manager"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    return user


def require_emergency_officer(user: User = Depends(get_current_user)) -> User:
    """Least-privilege: only an administrator or emergency officer may send alerts."""
    if user.role not in ("administrator", "emergency_officer"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Emergency-officer access required to send alerts")
    return user
