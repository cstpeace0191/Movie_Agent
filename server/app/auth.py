import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from argon2 import PasswordHasher
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from server.app.config import settings
from server.app.db import get_db
from server.app.models import Session as DBSession
from server.app.models import User

ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return ph.verify(hashed, password)
    except Exception:
        return False


def hash_token(token: str) -> str:
    """Hash an opaque token using SHA-256 for secure database lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, str, DBSession]:
    """Generate a new session, storing token_hash in DB and returning (raw_token, csrf_token, session)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    session_row = DBSession(
        token_hash=token_hash,
        user_id=user.id,
        csrf_token=csrf_token,
        created_at=now,
        last_seen_at=now,
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return raw_token, csrf_token, session_row


def invalidate_session(db: Session, raw_token: str) -> None:
    """Invalidate and remove an active session from the database."""
    token_hash = hash_token(raw_token)
    session_row = db.query(DBSession).filter(DBSession.token_hash == token_hash).first()
    if session_row:
        db.delete(session_row)
        db.commit()


async def get_current_session(
    movie_session: Annotated[str | None, Cookie()] = None,
    db: Session = Depends(get_db),
) -> tuple[User, DBSession]:
    """Extract and validate the current authenticated user session from cookie."""
    if not movie_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Authentication required"},
        )

    token_hash = hash_token(movie_session)
    session_row = db.query(DBSession).filter(DBSession.token_hash == token_hash).first()
    if not session_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Invalid or expired session"},
        )

    now = datetime.now(timezone.utc)
    expiry = session_row.last_seen_at.replace(tzinfo=timezone.utc) + timedelta(
        days=settings.SESSION_LIFETIME_DAYS
    )
    if now > expiry:
        db.delete(session_row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "Session expired"},
        )

    # Update last_seen_at at most once every 60 seconds to avoid SQLite write lock contention
    last_seen = session_row.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if (now - last_seen).total_seconds() > 60:
        session_row.last_seen_at = now
        db.commit()

    user = db.query(User).filter(User.id == session_row.user_id).first()
    if not user:
        db.delete(session_row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "not_authenticated", "message": "User not found"},
        )

    return user, session_row


async def require_user(
    session_info: tuple[User, DBSession] = Depends(get_current_session),
) -> User:
    return session_info[0]


async def require_csrf(
    request: Request,
    x_csrf_token: Annotated[str | None, Header()] = None,
    session_info: tuple[User, DBSession] = Depends(get_current_session),
) -> None:
    if request.method in ("POST", "DELETE", "PUT", "PATCH"):
        _, session_row = session_info
        if not x_csrf_token or x_csrf_token != session_row.csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "csrf_failed", "message": "Invalid or missing CSRF token"},
            )
