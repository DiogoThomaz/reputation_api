from __future__ import annotations

import pytest

from api.services.password_service import PasswordService
from api.services.user_service import UserService


pytestmark = pytest.mark.integration


def test_user_service_create_and_lookup_and_update_token(writable_db, created_emails, unique_email):
    service = UserService(writable_db)
    created_emails.append(unique_email)

    created = service.create_user(
        nome="Integracao Usuario",
        email=unique_email,
        senha_hash=PasswordService.hash_password("SenhaForte123"),
        role="USUARIO_PLANO_TESTE",
    )

    found_by_email = service.get_user_by_email(unique_email)
    assert found_by_email is not None
    assert found_by_email.id == created.id

    updated = service.update_token(created.id, "token-integracao-1")
    assert updated.token == "token-integracao-1"

    found_by_token = service.get_user_by_token("token-integracao-1")
    assert found_by_token is not None
    assert found_by_token.email == unique_email


def test_user_service_returns_none_for_missing_user(db):
    service = UserService(db)

    result = service.get_user_by_email("it_auth_inexistente@email.com")

    assert result is None
