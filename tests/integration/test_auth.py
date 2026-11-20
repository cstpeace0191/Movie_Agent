import pytest
from httpx import ASGITransport, AsyncClient

from server.app.main import app


@pytest.mark.asyncio
async def test_auth_workflow():
    from server.app.db import SessionLocal
    from server.app.models import User

    db = SessionLocal()
    db.query(User).filter(
        User.username_lower.in_(["alice_test", "bob_user", "unknown_user"])
    ).delete()
    db.commit()
    db.close()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Unauthenticated /api/auth/me returns 401 not_authenticated
        res = await client.get("/api/auth/me")
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "not_authenticated"

        # 2. Register new user
        reg_payload = {"username": "alice_test", "password": "supersecretpassword123"}
        res = await client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 201
        data = res.json()
        assert data["username"] == "alice_test"
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

        # Register again with same username -> 409 username_taken
        res = await client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 409
        assert res.json()["error"]["code"] == "username_taken"

        # Case-insensitive check: ALICE_TEST -> 409 username_taken
        res = await client.post(
            "/api/auth/register",
            json={"username": "ALICE_TEST", "password": "supersecretpassword123"},
        )
        assert res.status_code == 409

        # Register with invalid password (< 12 chars) -> 422 validation_failed
        res = await client.post(
            "/api/auth/register", json={"username": "bob_user", "password": "short"}
        )
        assert res.status_code == 422
        assert res.json()["error"]["code"] == "validation_failed"

        # 3. Login with wrong password -> 401 invalid_credentials
        res = await client.post(
            "/api/auth/login", json={"username": "alice_test", "password": "wrongpassword123"}
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "invalid_credentials"

        # Login with unknown user -> same 401 invalid_credentials
        res = await client.post(
            "/api/auth/login", json={"username": "unknown_user", "password": "wrongpassword123"}
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "invalid_credentials"

        # 4. Successful login
        res = await client.post("/api/auth/login", json=reg_payload)
        assert res.status_code == 200
        login_data = res.json()
        assert login_data["username"] == "alice_test"
        csrf_token = login_data["csrf_token"]
        assert csrf_token is not None
        assert "movie_session" in res.cookies

        # 5. Check /api/auth/me with cookies
        res = await client.get("/api/auth/me", cookies=res.cookies)
        assert res.status_code == 200
        assert res.json()["username"] == "alice_test"

        # 6. Logout without CSRF header -> 403 csrf_failed
        res = await client.post("/api/auth/logout", cookies=res.cookies)
        assert res.status_code == 403
        assert res.json()["error"]["code"] == "csrf_failed"

        # Logout with CSRF header -> 204
        headers = {"X-CSRF-Token": csrf_token}
        res = await client.post("/api/auth/logout", headers=headers, cookies=res.cookies)
        assert res.status_code == 204
