import email
import logging
import re
from email import policy
from typing import Any

from aiosmtpd.controller import Controller

from server.app.config import settings
from server.app.db import SessionLocal
from server.app.models import SentEmail

logger = logging.getLogger("mail_server")

_controller: Controller | None = None


def extract_verification_code(text: str) -> str | None:
    """Extract a 6-digit numeric verification code from email text."""
    matches = re.findall(r"\b(\d{6})\b", text)
    return matches[0] if matches else None


def record_email_to_db(
    recipient: str,
    sender: str,
    subject: str,
    body_text: str,
    verification_code: str | None = None,
    status: str = "delivered",
) -> SentEmail:
    """Persist an email record into the sent_emails table."""
    db = SessionLocal()
    try:
        code = verification_code or extract_verification_code(body_text)
        email_record = SentEmail(
            recipient=recipient,
            sender=sender,
            subject=subject,
            body_text=body_text,
            verification_code=code,
            status=status,
        )
        db.add(email_record)
        db.commit()
        db.refresh(email_record)
        return email_record
    finally:
        db.close()


class MovieMakerMailHandler:
    """aiosmtpd handler to accept incoming SMTP messages and record them."""

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:
        try:
            raw_content = envelope.content
            if isinstance(raw_content, str):
                raw_bytes = raw_content.encode("utf-8", errors="replace")
            else:
                raw_bytes = bytes(raw_content)

            parsed_msg = email.message_from_bytes(raw_bytes, policy=policy.default)
            subject = str(parsed_msg.get("Subject", "(No Subject)"))
            sender = envelope.mail_from or str(parsed_msg.get("From", "unknown@moviemaker.local"))
            rcpt_list = envelope.rcpt_tos or [str(parsed_msg.get("To", "user@moviemaker.local"))]

            # Extract text body
            body_text = ""
            if parsed_msg.is_multipart():
                for part in parsed_msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body_text = payload.decode(
                                part.get_content_charset() or "utf-8", errors="replace"
                            )
                            break
            else:
                payload = parsed_msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    body_text = payload.decode(
                        parsed_msg.get_content_charset() or "utf-8", errors="replace"
                    )
                else:
                    body_text = str(parsed_msg.get_payload())

            code = extract_verification_code(body_text)

            for rcpt in rcpt_list:
                record_email_to_db(
                    recipient=rcpt,
                    sender=sender,
                    subject=subject,
                    body_text=body_text,
                    verification_code=code,
                    status="delivered",
                )
                logger.info(
                    f"[AIOSMTPD] Successfully received & stored email for '{rcpt}' (Subject: {subject}, Code: {code})"
                )

            return "250 Message accepted for delivery by Movie Maker Python Mail Server"
        except Exception as exc:
            logger.error(f"[AIOSMTPD] Error processing incoming mail: {exc}")
            return "451 Internal server error"


def start_mail_server() -> bool:
    """Start the background aiosmtpd SMTP mail server."""
    global _controller
    if not settings.MAIL_SERVER_ENABLED:
        logger.info("[AIOSMTPD] Mail server is disabled by configuration.")
        return False

    if _controller is not None:
        return True

    try:
        handler = MovieMakerMailHandler()
        # Bind to host & port
        _controller = Controller(
            handler,
            hostname=settings.MAIL_SERVER_HOST,
            port=settings.MAIL_SERVER_PORT,
        )
        _controller.start()
        logger.info(
            f"[AIOSMTPD] Python aiosmtpd mail server successfully started on {settings.MAIL_SERVER_HOST}:{settings.MAIL_SERVER_PORT}"
        )
        return True
    except Exception as exc:
        logger.warning(
            f"[AIOSMTPD] Could not start aiosmtpd on {settings.MAIL_SERVER_HOST}:{settings.MAIL_SERVER_PORT}: {exc}"
        )
        _controller = None
        return False


def stop_mail_server() -> None:
    """Stop the background aiosmtpd SMTP mail server."""
    global _controller
    if _controller is not None:
        try:
            _controller.stop()
            logger.info("[AIOSMTPD] Mail server stopped.")
        except Exception as exc:
            logger.warning(f"[AIOSMTPD] Error stopping mail server: {exc}")
        finally:
            _controller = None
