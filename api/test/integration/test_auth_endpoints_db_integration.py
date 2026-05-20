from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app


pytestmark = pytest.mark.integration


@pytest.fixture
def client(writable_db):
    app.state.db = writable_db
    return TestClient(app)


def test_auth_endpoints_register_login_me_rotate_flow(client, created_emails, unique_email):
    register_payload = {
        "nome": "Integracao Endpoint",
        "email": unique_email,
        "telefone": "11999999999",
        "senha": "SenhaForte123",
    }

    response_register = client.post("/auth/register", json=register_payload)
    assert response_register.status_code == 201
    created_emails.append(unique_email)

    response_duplicate = client.post("/auth/register", json=register_payload)
    assert response_duplicate.status_code == 409

    response_login = client.post(
        "/auth/login",
        json={"email": unique_email, "senha": "SenhaForte123"},
    )
    assert response_login.status_code == 200
    token_1 = response_login.json()["token"]
    assert token_1

    response_me_fail = client.get("/auth/me")
    assert response_me_fail.status_code == 401

    response_me = client.get("/auth/me", headers={"Authorization": f"Bearer {token_1}"})
    assert response_me.status_code == 200
    assert response_me.json()["email"] == unique_email

    response_rotate = client.post(
        "/auth/rotate-token",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert response_rotate.status_code == 200
    token_2 = response_rotate.json()["token"]
    assert token_2
    assert token_2 != token_1

    response_old_token = client.get("/auth/me", headers={"Authorization": f"Bearer {token_1}"})
    assert response_old_token.status_code == 401

    response_new_token = client.get("/auth/me", headers={"Authorization": f"Bearer {token_2}"})
    assert response_new_token.status_code == 200
