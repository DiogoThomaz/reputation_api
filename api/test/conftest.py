from __future__ import annotations

from datetime import datetime, timezone

import pytest

from api.models import UserModel


@pytest.fixture
def user_row() -> dict:
    return {
        "id": 1,
        "created_at": datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
        "nome": "Diogo",
        "email": "diogo@email.com",
        "senha": "pbkdf2_sha256$260000$salt$hash",
        "token": "token-atual",
        "role": "USUARIO_PLANO_TESTE",
    }


@pytest.fixture
def user_model(user_row: dict) -> UserModel:
    return UserModel.from_row(user_row)
