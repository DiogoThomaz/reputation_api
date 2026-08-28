from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app


pytestmark = pytest.mark.integration


@pytest.fixture
def client(writable_db):
    app.state.db = writable_db
    return TestClient(app)


def test_health_e_frontend_sem_autenticacao(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200  # frontend HTML servido
    # auth removido do produto (MVP cru)
    assert client.post("/auth/login", json={}).status_code == 404


def test_recent_retorna_linhas_do_banco(client):
    response = client.get("/recent")
    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert isinstance(body["rows"], list)


def test_collect_valida_payload(client):
    # nome curto demais
    assert client.post("/collect", json={"app_id": "x"}).status_code == 422
    # count acima do limite
    assert client.post("/collect", json={"app_id": "nubank", "count": 999999}).status_code == 422


def test_stream_de_job_inexistente_da_404(client):
    assert client.get("/stream/nao-existe").status_code == 404