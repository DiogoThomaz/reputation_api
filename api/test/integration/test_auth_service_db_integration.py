from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.services.auth_service import AuthService
from api.services.password_service import PasswordService
from api.services.user_service import UserService


pytestmark = pytest.mark.integration


def test_auth_service_register_and_duplicate_email(writable_db, created_emails, unique_email):
    auth = AuthService(UserService(writable_db))
    created_emails.append(unique_email)

    user = auth.register(nome="Integracao Auth", email=unique_email, senha="SenhaForte123")
    assert user.email == unique_email
    assert user.role == "USUARIO_PLANO_TESTE"

    with pytest.raises(HTTPException) as exc:
        auth.register(nome="Integracao Auth", email=unique_email, senha="SenhaForte123")

    assert exc.value.status_code == 409


def test_auth_service_login_and_rotate_token(writable_db, created_emails, unique_email):
    user_service = UserService(writable_db)
    auth = AuthService(user_service)
    created_emails.append(unique_email)

    user_service.create_user(
        nome="Integracao Login",
        email=unique_email,
        senha_hash=PasswordService.hash_password("SenhaForte123"),
        role="USUARIO_PLANO_TESTE",
    )

    token_1, user_1 = auth.login(email=unique_email, senha="SenhaForte123")
    assert token_1
    assert user_1.email == unique_email

    found_1 = user_service.get_user_by_token(token_1)
    assert found_1 is not None
    assert found_1.email == unique_email

    token_2 = auth.rotate_token(user_1.id)
    assert token_2
    assert token_2 != token_1

    found_old = user_service.get_user_by_token(token_1)
    assert found_old is None

    found_new = user_service.get_user_by_token(token_2)
    assert found_new is not None
    assert found_new.email == unique_email
