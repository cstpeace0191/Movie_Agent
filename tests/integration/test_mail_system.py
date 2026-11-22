import pytest
from httpx import ASGITransport, AsyncClient

from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import SentEmail, User
from server.worker.tasks import send_verification_email_task


@pytest.mark.asyncio
async def test_mail_system_e2e():
    test_email = "mail_tester_99@example.com"
    username = "mail_tester_99"

    # Clean up test records
    db = SessionLocal()
    db.query(SentEmail).filter(SentEmail.recipient == test_email).delete()
    db.query(User).filter(User.username_lower == username).delete()
    db.commit()
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register a new user with an email
        reg_res = await client.post(
            "/api/auth/register",
            json={
                "username": username,
                "password": "validpassword1234",
                "email": test_email,
            },
        )
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert reg_data["verification_required"] is True

        # 2. Check the Mail API inbox
        inbox_res = await client.get(f"/api/mail/inbox?email={test_email}")
        assert inbox_res.status_code == 200
        inbox_data = inbox_res.json()
        assert len(inbox_data) >= 1
        assert inbox_data[0]["recipient"] == test_email
        assert inbox_data[0]["verification_code"] is not None

        # 3. Check the Mail API latest endpoint
        latest_res = await client.get(f"/api/mail/latest?email={test_email}")
        assert latest_res.status_code == 200
        latest_data = latest_res.json()
        code = latest_data["verification_code"]
        assert code is not None
        assert len(code) == 6

        # 4. Verify email using the code received by the mail server
        verify_res = await client.post(
            "/api/auth/verify-email",
            json={"username": username, "code": code},
        )
        assert verify_res.status_code == 200
        v_data = verify_res.json()
        assert v_data["success"] is True
        assert v_data["message_ko"] == "인증되었습니다"
        assert v_data["message_en"] == "You are Verified"

        # 5. Direct test of Celery worker email task
        send_verification_email_task(
            to_email="worker_test@example.com",
            code="654321",
            username="worker_tester",
        )
        # Should persist the email
        worker_latest = await client.get("/api/mail/latest?email=worker_test@example.com")
        assert worker_latest.status_code == 200
        assert worker_latest.json()["verification_code"] == "654321"
