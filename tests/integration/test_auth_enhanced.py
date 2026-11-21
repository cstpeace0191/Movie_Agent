import pytest
from httpx import ASGITransport, AsyncClient

from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import User


@pytest.mark.asyncio
async def test_enhanced_auth_workflow():
    db = SessionLocal()
    db.query(User).filter(User.username_lower.in_(["new_tester_1", "email_tester_2"])).delete()
    db.commit()
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Check username availability for new user
        res = await client.get("/api/auth/check-username?username=new_tester_1")
        assert res.status_code == 200
        assert res.json()["available"] is True

        # Check invalid username
        res = await client.get("/api/auth/check-username?username=a")
        assert res.status_code == 200
        assert res.json()["available"] is False

        # 2. Register user with invalid email format -> 422
        res = await client.post(
            "/api/auth/register",
            json={
                "username": "email_tester_2",
                "password": "validpassword1234",
                "email": "not-an-email",
            },
        )
        assert res.status_code == 422

        # 3. Register user with valid email -> 201 and verification_required=True
        res = await client.post(
            "/api/auth/register",
            json={
                "username": "email_tester_2",
                "password": "validpassword1234",
                "country": "KR",
                "phone": "010-1234-5678",
                "email": "tester@example.com",
            },
        )
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "email_tester_2"
        assert data["verification_required"] is True
        code = data["debug_code"]
        assert code is not None
        assert len(code) == 6

        # Check availability again -> now taken
        res = await client.get("/api/auth/check-username?username=email_tester_2")
        assert res.status_code == 200
        assert res.json()["available"] is False

        # 3b. Attempt to register another account with the SAME email -> 409 email_taken
        res_dup_email = await client.post(
            "/api/auth/register",
            json={
                "username": "different_user_email",
                "password": "validpassword1234",
                "email": "tester@example.com",
            },
        )
        assert res_dup_email.status_code == 409
        assert res_dup_email.json()["error"]["code"] == "email_taken"

        # 3c. Attempt to register another account with the SAME phone -> 409 phone_taken
        res_dup_phone = await client.post(
            "/api/auth/register",
            json={
                "username": "different_user_phone",
                "password": "validpassword1234",
                "phone": "010-1234-5678",
                "email": "different_email@example.com",
            },
        )
        assert res_dup_phone.status_code == 409
        assert res_dup_phone.json()["error"]["code"] == "phone_taken"

        # 4. Attempt login before verification -> 403 email_not_verified
        res = await client.post(
            "/api/auth/login",
            json={"username": "email_tester_2", "password": "validpassword1234"},
        )
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "email_not_verified"

        # 5. Verify email with wrong code -> 400
        res = await client.post(
            "/api/auth/verify-email",
            json={"username": "email_tester_2", "code": "000000"},
        )
        assert res.status_code == 400

        # 5b. Resend verification code
        res = await client.post(
            "/api/auth/resend-code",
            json={"username": "email_tester_2"},
        )
        assert res.status_code == 200
        resend_data = res.json()
        assert resend_data["success"] is True
        assert resend_data["code"] is not None
        new_code = resend_data["code"]

        # 6. Verify email with correct code -> 200
        res = await client.post(
            "/api/auth/verify-email",
            json={"username": "email_tester_2", "code": new_code},
        )
        assert res.status_code == 200
        v_data = res.json()
        assert v_data["success"] is True
        assert v_data["message_ko"] == "인증되었습니다"
        assert v_data["message_en"] == "You are Verified"

        # 7. Login after verification -> 200
        res = await client.post(
            "/api/auth/login",
            json={"username": "email_tester_2", "password": "validpassword1234"},
        )
        assert res.status_code == 200
        assert "movie_session" in res.cookies
