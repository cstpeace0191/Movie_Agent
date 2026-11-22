import pytest
from httpx import ASGITransport, AsyncClient

from server.app.auth import create_session, hash_password
from server.app.config import settings
from server.app.db import SessionLocal
from server.app.main import app
from server.app.models import User


@pytest.fixture
def auth_cookies():
    db = SessionLocal()
    user = db.query(User).filter(User.username == "engine_tester").first()
    if not user:
        user = User(
            username="engine_tester",
            username_lower="engine_tester",
            password_hash=hash_password("password123456"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    raw_token, _, _ = create_session(db, user)
    db.close()
    return {"movie_session": raw_token}


@pytest.mark.asyncio
async def test_get_providers_list(auth_cookies, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=auth_cookies
    ) as client:
        res = await client.get("/api/providers")
        assert res.status_code == 200
        providers = res.json()
        prov_map = {p["id"]: p for p in providers}

        assert "ltx-2.3" in prov_map
        assert prov_map["ltx-2.3"]["enabled"] is True
        assert prov_map["ltx-2.3"]["location"] == "local"

        assert "gemini-omni-1.2-flash" in prov_map
        gemini = prov_map["gemini-omni-1.2-flash"]
        assert gemini["location"] == "cloud"
        assert gemini["sends_data_externally"] is True
        assert gemini["enabled"] is False
        assert gemini["disabled_reason"] is not None


@pytest.mark.asyncio
async def test_providers_expose_capability_flags(auth_cookies):
    """Feature 002: each provider reports requires_photos from its class (contract delta)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=auth_cookies
    ) as client:
        res = await client.get("/api/providers")
        assert res.status_code == 200
        for p in res.json():
            assert isinstance(p["requires_photos"], bool)
            assert isinstance(p["sends_data_externally"], bool)
        prov_map = {p["id"]: p for p in res.json()}
        assert prov_map["ltx-2.3"]["requires_photos"] is False
        assert prov_map["gemini-omni-1.2-flash"]["sends_data_externally"] is True
        assert prov_map["mock"]["sends_data_externally"] is False
