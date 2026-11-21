import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from server.app.db import get_db
from server.app.models import SentEmail
from server.app.schemas import MailMessageOut

logger = logging.getLogger("mail_api")
router = APIRouter(prefix="/api/mail", tags=["mail"])


@router.get("/inbox", response_model=list[MailMessageOut])
def get_inbox(
    email: str | None = Query(None, description="Optional recipient email to filter by"),
    db: Session = Depends(get_db),
):
    query = db.query(SentEmail)
    if email and email.strip():
        query = query.filter(SentEmail.recipient == email.strip())
    results = query.order_by(SentEmail.created_at.desc()).limit(20).all()
    return results


@router.get("/latest", response_model=MailMessageOut)
def get_latest_email(
    email: str = Query(..., description="Recipient email address"),
    db: Session = Depends(get_db),
):
    clean_email = email.strip()
    msg = (
        db.query(SentEmail)
        .filter(SentEmail.recipient == clean_email)
        .order_by(SentEmail.created_at.desc())
        .first()
    )
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "email_not_found", "message": f"No email found for {clean_email}"},
        )
    return msg


@router.get("/{mail_id}", response_model=MailMessageOut)
def get_email_by_id(mail_id: str, db: Session = Depends(get_db)):
    msg = db.query(SentEmail).filter(SentEmail.id == mail_id).first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "email_not_found", "message": "Email not found"},
        )
    return msg
