from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from server.app.auth import (
    create_session,
    get_current_session,
    hash_password,
    invalidate_session,
    require_csrf,
    verify_password,
)
from server.app.db import get_db
from server.app.models import User, validate_password, validate_username
from server.app.schemas import LoginResponse, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    if not validate_username(user_in.username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_failed",
                "message": "Username must be 3-32 characters of letters, digits, or underscore",
            },
        )
    if not validate_password(user_in.password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "validation_failed",
                "message": "Password must be at least 12 characters",
            },
        )

    existing = db.query(User).filter(User.username_lower == user_in.username.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "username_taken", "message": "Username is already taken"},
        )

    hashed = hash_password(user_in.password)
    user = User(
        username=user_in.username,
        username_lower=user_in.username.lower(),
        password_hash=hashed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut(id=user.id, username=user.username)


@router.post("/login", response_model=LoginResponse)
def login(login_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username_lower == login_in.username.lower()).first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid username or password"},
        )

    raw_token, csrf_token, _ = create_session(db, user)
    response.set_cookie(
        key="movie_session",
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=False,  # Can be true in production with HTTPS
    )
    return LoginResponse(id=user.id, username=user.username, csrf_token=csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    movie_session: Annotated[str | None, Cookie()] = None,
    csrf_check: None = Depends(require_csrf),
    db: Session = Depends(get_db),
):
    if movie_session:
        invalidate_session(db, movie_session)
    response.delete_cookie(key="movie_session")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=LoginResponse)
def me(session_info: tuple[User, Any] = Depends(get_current_session)):
    user, session_row = session_info
    return LoginResponse(id=user.id, username=user.username, csrf_token=str(session_row.csrf_token))
