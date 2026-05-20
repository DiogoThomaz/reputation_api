from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from api.middlewares.access_log_middleware import AccessLogMiddleware
from api.middlewares.auth_middleware import AuthMiddleware
from api.models import UserModel


class RecordingDB:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append({"query": query, "params": params})
        return {"rowcount": 1, "rows": []}


def _log_fields(call):
    params = call["params"]
    return {
        "ip": params[0],
        "user_agent": params[1],
        "method": params[2],
        "path": params[3],
        "payload": params[4],
        "status": params[5],
        "elapsed_ms": params[6],
    }


def _build_app(db: RecordingDB) -> FastAPI:
    app = FastAPI()
    app.state.db = db
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AccessLogMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/protected")
    def protected(request: Request):
        return {"user_id": request.state.user.id}

    @app.post("/protected/items")
    def create_item(payload: dict):
        return {"received": payload}

    @app.get("/boom")
    def boom():
        raise RuntimeError("downstream failure")

    return app


def _patch_user_lookup(monkeypatch: MonkeyPatch, user: UserModel):
    calls = []

    def fake_get_user_by_token(self, token):
        calls.append(token)
        if token == "valid-token":
            return user
        return None

    monkeypatch.setattr("api.services.user_service.UserService.get_user_by_token", fake_get_user_by_token)
    return calls


def test_public_route_skips_auth_lookup_and_writes_access_log(monkeypatch: MonkeyPatch, user_model: UserModel):
    db = RecordingDB()
    auth_calls = _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(db))

    response = client.get("/health", headers={"user-agent": "pytest"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert auth_calls == []
    assert len(db.calls) == 1
    log = _log_fields(db.calls[0])
    assert log["method"] == "GET"
    assert log["path"] == "/health"
    assert log["status"] == 200
    assert log["user_agent"] == "pytest"


def test_protected_route_without_token_is_blocked_and_logged(monkeypatch: MonkeyPatch, user_model: UserModel):
    db = RecordingDB()
    auth_calls = _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(db))

    response = client.get("/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == "Token ausente ou formato invalido"
    assert auth_calls == []
    assert len(db.calls) == 1
    log = _log_fields(db.calls[0])
    assert log["method"] == "GET"
    assert log["path"] == "/protected"
    assert log["status"] == 401


def test_protected_route_with_valid_token_sets_user_and_is_logged(monkeypatch: MonkeyPatch, user_model: UserModel):
    db = RecordingDB()
    auth_calls = _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(db))

    response = client.get("/protected", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 200
    assert response.json() == {"user_id": user_model.id}
    assert auth_calls == ["valid-token"]
    assert len(db.calls) == 1
    log = _log_fields(db.calls[0])
    assert log["method"] == "GET"
    assert log["path"] == "/protected"
    assert log["status"] == 200


def test_json_payload_is_preserved_and_logged(monkeypatch: MonkeyPatch, user_model: UserModel):
    db = RecordingDB()
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(db))

    response = client.post(
        "/protected/items",
        json={"name": "Produto", "quantity": 2},
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"received": {"name": "Produto", "quantity": 2}}
    assert len(db.calls) == 1
    assert "%s" in db.calls[0]["query"]
    log = _log_fields(db.calls[0])
    assert log["method"] == "POST"
    assert log["path"] == "/protected/items"
    assert log["status"] == 200
    assert json.loads(log["payload"]) == {"name": "Produto", "quantity": 2}


def test_downstream_error_is_logged_with_500(monkeypatch: MonkeyPatch, user_model: UserModel):
    db = RecordingDB()
    _patch_user_lookup(monkeypatch, user_model)
    client = TestClient(_build_app(db), raise_server_exceptions=False)

    response = client.get("/boom", headers={"Authorization": "Bearer valid-token"})

    assert response.status_code == 500
    assert len(db.calls) == 1
    log = _log_fields(db.calls[0])
    assert log["method"] == "GET"
    assert log["path"] == "/boom"
    assert log["status"] == 500
