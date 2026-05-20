from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middlewares.access_log_middleware import AccessLogMiddleware


class RecordingDB:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append({"query": query, "params": params})
        return {"rowcount": 1, "rows": []}


class FailingDB:
    def execute(self, query, params=None):
        raise RuntimeError("database unavailable")


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


def test_access_log_is_saved_after_request():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.get("/health", headers={"user-agent": "pytest", "x-forwarded-for": "10.0.0.1, 10.0.0.2"})

    assert response.status_code == 200
    assert len(db.calls) == 1
    query = db.calls[0]["query"]
    params = db.calls[0]["params"]
    assert "INSERT INTO logs_acesso" in query
    assert params[0] == "10.0.0.1"
    assert params[1] == "pytest"
    assert params[2] == "GET"
    assert params[3] == "/health"
    assert params[4] is None
    assert params[5] == 200
    assert isinstance(params[6], float)


def test_access_log_saves_json_payload():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.post("/items", json={"name": "Produto", "quantity": 2})

    assert response.status_code == 200
    payload = json.loads(db.calls[0]["params"][4])
    assert payload == {"name": "Produto", "quantity": 2}


def test_access_log_records_not_found_response():
    db = RecordingDB()
    client = TestClient(_build_app(db))

    response = client.get("/missing")

    assert response.status_code == 404
    assert db.calls[0]["params"][2] == "GET"
    assert db.calls[0]["params"][3] == "/missing"
    assert db.calls[0]["params"][5] == 404


def test_access_log_database_failure_does_not_break_response():
    client = TestClient(_build_app(FailingDB()))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
