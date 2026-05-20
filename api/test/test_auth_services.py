from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from api.services.auth_service import AuthService
from api.services.token_service import TokenService
from api.services.user_service import UserService


class FakeDB:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        return self.responses.pop(0)


def test_auth_register_creates_user_with_default_role(user_model):
    user_service = Mock()
    user_service.get_user_by_email.return_value = None
    user_service.create_user.return_value = user_model

    with patch("api.services.auth_service.PasswordService.hash_password", return_value="HASH") as hash_mock:
        service = AuthService(user_service=user_service)
        result = service.register(nome="Diogo", email="diogo@email.com", senha="12345678")

    hash_mock.assert_called_once_with("12345678")
    user_service.create_user.assert_called_once_with(
        nome="Diogo",
        email="diogo@email.com",
        senha_hash="HASH",
        role="USUARIO_PLANO_TESTE",
    )
    assert result.email == "diogo@email.com"


def test_auth_login_rejects_invalid_credentials():
    user_service = Mock()
    user_service.get_user_by_email.return_value = None
    service = AuthService(user_service=user_service)

    with pytest.raises(HTTPException) as exc:
        service.login(email="naoexiste@email.com", senha="12345678")

    assert exc.value.status_code == 401


def test_auth_login_updates_token(user_model):
    user_service = Mock()
    user_service.get_user_by_email.return_value = user_model
    user_service.update_token.return_value = user_model

    with patch("api.services.auth_service.PasswordService.verify_password", return_value=True):
        with patch("api.services.auth_service.TokenService.generate_token", return_value="novo-token"):
            service = AuthService(user_service=user_service)
            token, user = service.login(email="diogo@email.com", senha="12345678")

    assert token == "novo-token"
    user_service.update_token.assert_called_once_with(1, "novo-token")
    assert user.id == 1


def test_auth_rotate_token_calls_update(user_model):
    user_service = Mock()
    user_service.update_token.return_value = user_model

    with patch("api.services.auth_service.TokenService.generate_token", return_value="rotated-token"):
        service = AuthService(user_service=user_service)
        token = service.rotate_token(user_id=1)

    assert token == "rotated-token"
    user_service.update_token.assert_called_once_with(1, "rotated-token")


def test_user_service_get_by_email_returns_none_when_missing():
    db = FakeDB(responses=[{"rowcount": 0, "rows": []}])
    service = UserService(db=db)

    result = service.get_user_by_email("vazio@email.com")

    assert result is None
    assert "WHERE email = %s" in db.calls[0][0]


def test_user_service_create_user_and_update_token(user_row):
    created_row = dict(user_row)
    updated_row = dict(user_row)
    updated_row["token"] = "token-novo"
    db = FakeDB(
        responses=[
            {"rowcount": 1, "rows": [created_row]},
            {"rowcount": 1, "rows": [updated_row]},
        ]
    )
    service = UserService(db=db)

    created = service.create_user("Diogo", "diogo@email.com", "HASH", "USUARIO_PLANO_TESTE")
    updated = service.update_token(created.id, "token-novo")

    assert "INSERT INTO usuarios" in db.calls[0][0]
    assert db.calls[0][1] == ("Diogo", "diogo@email.com", "HASH", "USUARIO_PLANO_TESTE")
    assert "UPDATE usuarios" in db.calls[1][0]
    assert db.calls[1][1] == ("token-novo", created.id)
    assert updated.token == "token-novo"


def test_token_service_generates_random_non_empty_tokens():
    token_a = TokenService.generate_token()
    token_b = TokenService.generate_token()

    assert token_a
    assert token_b
    assert token_a != token_b
