import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from server.app.config import settings
from server.app.mail_server import record_email_to_db

logger = logging.getLogger("email")


def send_verification_email(to_email: str, code: str, username: str) -> bool:
    """Send verification email containing the 6-digit code to the user.

    1. If external SMTP_HOST is configured, sends via external SMTP.
    2. If external SMTP_HOST is not configured, dispatches via the internal
       Python aiosmtpd mail server on 127.0.0.1:MAIL_SERVER_PORT.
    3. Persists the email to SentEmail database table for instant In-App Mailbox retrieval.
    """
    subject = f"[Movie Maker] 이메일 인증 코드 (Verification Code): {code}"
    body_text = f"""안녕하세요 {username}님,

Movie Maker 계정 가입을 위한 6자리 인증 코드입니다:
인증 코드: {code}

이 코드는 15분 동안 유효합니다.
화면의 인증 코드 입력창에 위 번호를 입력하여 인증을 완료해 주세요.

감사합니다.
Movie Maker Team

--------------------------------------------------
Hello {username},

Here is your 6-digit verification code for Movie Maker:
Verification Code: {code}

This code is valid for 15 minutes.
Please enter this code on the verification screen to activate your account.

Thank you,
Movie Maker Team
"""

    # Always ensure email is recorded in the internal database for In-App Mailbox
    record_email_to_db(
        recipient=to_email,
        sender=settings.SMTP_FROM,
        subject=subject,
        body_text=body_text,
        verification_code=code,
        status="delivered",
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Determine target SMTP host & port
    target_host = settings.SMTP_HOST
    target_port = settings.SMTP_PORT
    is_external = bool(target_host)

    if not target_host:
        # Default to internal Python aiosmtpd server
        target_host = "127.0.0.1"
        target_port = settings.MAIL_SERVER_PORT

    try:
        if is_external and target_port == 465:
            server = smtplib.SMTP_SSL(target_host, target_port, timeout=10)
        else:
            server = smtplib.SMTP(target_host, target_port, timeout=10)
            if is_external and settings.SMTP_TLS:
                server.starttls()

        if is_external and settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
        server.quit()
        logger.info(
            f"[EMAIL_DISPATCH] Verification email successfully sent to '{to_email}' via {'External SMTP' if is_external else 'Python aiosmtpd'} ({target_host}:{target_port})."
        )
        return True
    except Exception as exc:
        logger.warning(
            f"[EMAIL_DISPATCH] SMTP socket delivery to {target_host}:{target_port} encountered ({exc}). Local record preserved in In-App Mailbox."
        )
        return False
