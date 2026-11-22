import logging
import re
import secrets
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response, status
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
from server.app.email_sender import send_verification_email
from server.app.models import User, utcnow, validate_email, validate_password, validate_username
from server.app.schemas import (
    CheckUsernameResponse,
    LoginResponse,
    ResendCodeRequest,
    ResendCodeResponse,
    UserLogin,
    UserOut,
    UserRegister,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

logger = logging.getLogger("auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


def dispatch_verification_email(to_email: str, code: str, username: str) -> None:
    """Dispatch email via Celery worker and ensure immediate in-process recording."""
    # Always send and record email immediately so In-App Mailbox is up to date
    send_verification_email(to_email, code, username)
    try:
        from server.worker.tasks import send_verification_email_task

        send_verification_email_task.delay(to_email, code, username)
        logger.info(f"[EMAIL_DISPATCH] Queued Celery email worker task for {to_email}")
    except Exception as exc:
        logger.debug(f"[EMAIL_DISPATCH] Celery worker queue not active ({exc})")


@router.get("/check-username", response_model=CheckUsernameResponse)
def check_username(username: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    clean_username = username.strip()
    if not validate_username(clean_username):
        return CheckUsernameResponse(
            available=False,
            message="Username must be 3-32 characters of letters, digits, or underscore",
        )

    existing = db.query(User).filter(User.username_lower == clean_username.lower()).first()
    if existing:
        return CheckUsernameResponse(available=False, message="Username is already taken")

    return CheckUsernameResponse(available=True, message="Username is available")


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    clean_username = user_in.username.strip()
    if not validate_username(clean_username):
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

    # Validate and check uniqueness of email if provided
    clean_email = user_in.email.strip() if user_in.email and user_in.email.strip() else None
    if clean_email:
        if not validate_email(clean_email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "validation_failed",
                    "message": "Invalid email address format",
                },
            )
        existing_email = db.query(User).filter(User.email.ilike(clean_email)).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "email_taken", "message": "Email is already registered"},
            )

    # Check phone uniqueness if provided
    clean_phone = user_in.phone.strip() if user_in.phone and user_in.phone.strip() else None
    if clean_phone:
        normalized_phone = re.sub(r"[^\d+]", "", clean_phone)
        existing_phone = (
            db.query(User)
            .filter((User.phone == clean_phone) | (User.phone == normalized_phone))
            .first()
        )
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "phone_taken", "message": "Phone number is already registered"},
            )

    existing = db.query(User).filter(User.username_lower == clean_username.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "username_taken", "message": "Username is already taken"},
        )

    hashed = hash_password(user_in.password)

    # Determine email verification requirement
    verification_required = False
    verification_code = None
    verification_expires_at = None
    email_verified = True

    if clean_email:
        verification_required = True
        email_verified = False
        # Generate 6-digit numeric verification code
        verification_code = f"{secrets.randbelow(900000) + 100000}"
        verification_expires_at = utcnow() + timedelta(minutes=15)
        # Send verification email via Celery worker / aiosmtpd
        dispatch_verification_email(clean_email, verification_code, clean_username)
        logger.info(
            f"[EMAIL_VERIFICATION] Verification message dispatched to '{clean_email}' with code: {verification_code}"
        )

    user = User(
        username=clean_username,
        username_lower=clean_username.lower(),
        password_hash=hashed,
        country=user_in.country.strip() if user_in.country else None,
        phone=user_in.phone.strip() if user_in.phone else None,
        email=clean_email,
        email_verified=email_verified,
        verification_code=verification_code,
        verification_expires_at=verification_expires_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        country=user.country,
        phone=user.phone,
        email_verified=user.email_verified,
        verification_required=verification_required,
        debug_code=verification_code,
    )


@router.post("/verify-email", response_model=VerifyEmailResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    clean_username = payload.username.strip()
    clean_code = payload.code.strip()

    user = db.query(User).filter(User.username_lower == clean_username.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User not found"},
        )

    if user.email_verified:
        return VerifyEmailResponse(
            success=True,
            message_ko="인증되었습니다",
            message_en="You are Verified",
        )

    now = utcnow()
    exp = user.verification_expires_at
    is_expired = False
    if exp is not None:
        if exp.tzinfo is None and now.tzinfo is not None:
            exp = exp.replace(tzinfo=now.tzinfo)
        elif exp.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=exp.tzinfo)
        is_expired = exp < now

    if not user.verification_code or user.verification_code != clean_code or is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_verification_code",
                "message": "Invalid or expired verification code",
            },
        )

    user.email_verified = True
    user.verification_code = None
    user.verification_expires_at = None
    db.commit()

    return VerifyEmailResponse(
        success=True,
        message_ko="인증되었습니다",
        message_en="You are Verified",
    )


@router.post("/resend-code", response_model=ResendCodeResponse)
def resend_code(payload: ResendCodeRequest, db: Session = Depends(get_db)):
    clean_username = payload.username.strip()
    user = db.query(User).filter(User.username_lower == clean_username.lower()).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "user_not_found", "message": "User not found"},
        )

    if user.email_verified:
        return ResendCodeResponse(
            success=True,
            message="User email is already verified",
            email=user.email,
        )

    if not user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "no_email", "message": "No email registered for this user"},
        )

    # Generate new 6-digit code
    new_code = f"{secrets.randbelow(900000) + 100000}"
    user.verification_code = new_code
    user.verification_expires_at = utcnow() + timedelta(minutes=15)
    db.commit()

    dispatch_verification_email(user.email, new_code, user.username)
    logger.info(
        f"[EMAIL_VERIFICATION] Resent verification code to '{user.email}' for '{user.username}'"
    )

    return ResendCodeResponse(
        success=True,
        message="Verification code resent successfully",
        email=user.email,
        code=new_code,
    )


@router.post("/login", response_model=LoginResponse)
def login(login_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username_lower == login_in.username.lower()).first()
    if not user or not verify_password(login_in.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid username or password"},
        )

    # If email was registered but not yet verified
    if user.email and not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "email_not_verified",
                "message": "Please verify your email before logging in",
            },
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
