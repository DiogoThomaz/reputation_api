from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middlewares.access_log_middleware import AccessLogMiddleware
from api.middlewares.auth_middleware import AuthMiddleware


class RecordingDB:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append({"query": query, "params": params})
        return {"rowcount": 1, "rows": []}


class FailingDB:
    def execute(self, query, params=None):
        raise RuntimeError("database unavailable")


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


def _build_app(db):
    app = FastAPI()
    app.state.db = db
    app.add_middleware(AccessLogMiddleware)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/items")
    def create_item(payload: dict):
        return {"received": payload}

    return app


def _build_app_with_auth_and_access_log(db):
    app = FastAPI()
    app.state.db = db
    app.add_middleware(AuthMiddleware)
    app.add_middleware(AccessLogMiddleware)

    @app.get("/protected")
    def protected():
        return {"status": "ok"}

    return app


def test_access_log_is_saved_after_request():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.get("/health", headers={"user-agent": "pytest", "x-forwarded-for": "10.0.0.1, 10.0.0.2"})

    assert response.status_code == 200
    assert len(db.calls) == 1
    query = db.calls[0]["query"]
    log = _log_fields(db.calls[0])
    assert "INSERT INTO logs_acesso" in query
    assert "%s" in query
    assert log["ip"] == "10.0.0.1"
    assert log["user_agent"] == "pytest"
    assert log["method"] == "GET"
    assert log["path"] == "/health"
    assert log["payload"] is None
    assert log["status"] == 200
    assert isinstance(log["elapsed_ms"], float)


def test_each_request_sends_insert_to_database():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    first_response = client.get("/health")
    second_response = client.post("/items", json={"id": 123})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert len(db.calls) == 2
    assert all("INSERT INTO logs_acesso" in call["query"] for call in db.calls)
    assert [_log_fields(call)["method"] for call in db.calls] == ["GET", "POST"]
    assert [_log_fields(call)["path"] for call in db.calls] == ["/health", "/items"]


def test_access_log_saves_json_payload():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.post("/items", json={"name": "Produto", "quantity": 2})

    assert response.status_code == 200
    payload = json.loads(_log_fields(db.calls[0])["payload"])
    assert payload == {"name": "Produto", "quantity": 2}


def test_access_log_records_not_found_response():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.get("/missing")

    assert response.status_code == 404
    log = _log_fields(db.calls[0])
    assert log["method"] == "GET"
    assert log["path"] == "/missing"
    assert log["status"] == 404


def test_access_log_saves_request_blocked_by_auth_middleware():
    db = RecordingDB()
    client = TestClient(_build_app_with_auth_and_access_log(db))

    response = client.get("/protected")

    assert response.status_code == 401
    assert len(db.calls) == 1
    query = db.calls[0]["query"]
    log = _log_fields(db.calls[0])
    assert "INSERT INTO logs_acesso" in query
    assert log["method"] == "GET"
    assert log["path"] == "/protected"
    assert log["status"] == 401


def test_access_log_database_failure_does_not_break_response():
    client = TestClient(_build_app(FailingDB()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
