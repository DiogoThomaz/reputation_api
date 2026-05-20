from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.schemas.auth_schema import LoginRequest
from api.schemas.user_schema import RegisterRequest
from api.services.password_service import PasswordService


def test_password_is_stored_hashed_and_verifiable():
    plain = "SenhaSegura123"
    hashed = PasswordService.hash_password(plain)

    assert hashed != plain
    assert hashed.startswith("pbkdf2_sha256$")
    assert PasswordService.verify_password(plain, hashed) is True
    assert PasswordService.verify_password("OutraSenha", hashed) is False


def test_register_password_minimum_length_is_8():
    with pytest.raises(ValidationError):
        RegisterRequest(
            nome="Diogo",
            email="diogo@email.com",
            telefone="11999999999",
            senha="1234567",
        )


def test_login_password_minimum_length_is_8():
    with pytest.raises(ValidationError):
        LoginRequest(email="diogo@email.com", senha="1234567")
