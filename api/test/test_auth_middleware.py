from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api.middlewares.auth_middleware import AuthMiddleware
from api.models import UserModel


class DummyDB:
    pass


def _build_app(user):
    app = FastAPI()
    app.state.db = DummyDB()
    app.add_middleware(AuthMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/protected")
    def protected(request: Request):
        return {"user_id": request.state.user.id}

    return app


def _patch_user_lookup(monkeypatch, returned_user):
    def fake_get_user_by_token(self, token):
        if token == "valid-token":
            return returned_user
        return None

    monkeypatch.setattr("api.services.user_service.UserService.get_user_by_token", fake_get_user_by_token)


def test_public_route_is_accessible_without_token(monkeypatch, user_model: UserModel):
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(user_model))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_route_requires_token(monkeypatch, user_model: UserModel):
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(user_model))

    response = client.get("/protected")

    assert response.status_code == 401


def test_protected_route_rejects_invalid_token(monkeypatch, user_model: UserModel):
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(user_model))

    response = client.get("/protected", headers={"Authorization": "Bearer invalid-token"})

    assert response.status_code == 401


def test_protected_route_accepts_valid_token(monkeypatch, user_model: UserModel):
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(user_model))

    response = client.get("/protected", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json()["user_id"] == user_model.id
