from __future__ import annotations

from uuid import uuid4

import pytest

from reputation_worker.postgres import PostgresClient


pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def db() -> PostgresClient:
    return PostgresClient()


@pytest.fixture
def created_emails(db: PostgresClient):
    emails: list[str] = []
    try:
        yield emails
    finally:
        for email in emails:
            try:
                db.execute("DELETE FROM usuarios WHERE email = %s", (email,))
            except Exception:
                pass


@pytest.fixture
def unique_email() -> str:
    return f"it_auth_{uuid4().hex}@email.com"


@pytest.fixture
def writable_db(db: PostgresClient, unique_email: str):
    try:
        db.execute(
            (
                "INSERT INTO usuarios (nome, email, senha, role) "
                "VALUES (%s, %s, %s, %s)"
            ),
            ("Write Check", unique_email, "hash_teste", "USUARIO_PLANO_TESTE"),
        )
        db.execute("DELETE FROM usuarios WHERE email = %s", (unique_email,))
    except Exception as exc:
        pytest.skip(f"Banco atual sem permissao de escrita para usuarios: {exc}")

    return db
