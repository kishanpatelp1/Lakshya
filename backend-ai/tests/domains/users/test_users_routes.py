"""Unit tests for users domain routes behavior."""

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.domains.users import routes as user_routes


class _DummyUsersService:
    def __init__(self, db):
        self.db = db

    def get_user_profile(self, user_id):
        return {"id": str(user_id), "email": "demo@example.com"}

    def update_user_profile(self, user_id, update_data):
        return {"id": str(user_id), **update_data}

    async def upload_profile_pic(self, user_id, file):
        return {"profile_pic_url": f"/uploads/avatars/{user_id}.png"}

    def submit_kyc(self, user_id, pan_card_number, aadhaar_number):
        return {
            "user_id": str(user_id),
            "kyc_status": "pending",
            "pan": pan_card_number,
            "aadhaar": aadhaar_number,
        }

    def get_kyc_status(self, user_id):
        return {"user_id": str(user_id), "kyc_status": "pending"}

    def verify_kyc(self, user_id):
        return {"user_id": str(user_id), "kyc_status": "verified"}


def _make_client(monkeypatch):
    monkeypatch.setattr(user_routes, "UsersService", _DummyUsersService)
    app = FastAPI()

    def _fake_get_db():
        yield object()

    app.dependency_overrides[user_routes.get_db] = _fake_get_db
    app.include_router(user_routes.router)
    return TestClient(app)


def test_update_user_profile_route(monkeypatch):
    client = _make_client(monkeypatch)
    user_id = uuid4()

    response = client.put(
        f"/users/{user_id}",
        json={"full_name": "Demo User", "expertise_level": "advanced"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(user_id)
    assert body["full_name"] == "Demo User"
    assert body["expertise_level"] == "advanced"


def test_submit_kyc_route(monkeypatch):
    client = _make_client(monkeypatch)
    user_id = uuid4()

    response = client.post(
        f"/users/{user_id}/kyc/submit",
        json={"pan_card_number": "ABCDE1234F", "aadhaar_number": "123412341234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["kyc_status"] == "pending"


def test_verify_kyc_route(monkeypatch):
    client = _make_client(monkeypatch)
    user_id = uuid4()

    response = client.post(f"/users/{user_id}/kyc/verify")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["kyc_status"] == "verified"
