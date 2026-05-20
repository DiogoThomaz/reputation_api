from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.schemas.user_schema import RegisterRequest
from api.services.auth_service import AuthService


def test_register_rejects_existing_email(user_model):
    user_service = Mock()
    user_service.get_user_by_email.return_value = user_model
    service = AuthService(user_service=user_service)

    with pytest.raises(HTTPException) as exc:
        service.register(nome="Diogo", email="diogo@email.com", senha="12345678")

    assert exc.value.status_code == 409
    assert exc.value.detail == "Email ja cadastrado"


def test_register_request_rejects_malformed_email():
    with pytest.raises(ValidationError):
        RegisterRequest(
            nome="Diogo",
            email="email-sem-formato",
            telefone="11999999999",
            senha="12345678",
        )


def test_register_request_rejects_malformed_phone():
    with pytest.raises(ValidationError):
        RegisterRequest(
            nome="Diogo",
            email="diogo@email.com",
            telefone="11-99999-9999",
            senha="12345678",
        )
