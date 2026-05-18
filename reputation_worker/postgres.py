from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _load_env_file(env_path: str = ".env") -> None:
    """Carrega variaveis simples de um arquivo .env sem dependencias externas."""
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _import_psycopg():
    """Import tardio para permitir testes sem dependencia ativa em import time."""
    import psycopg  # type: ignore

    return psycopg


@dataclass(slots=True)
class PostgresSettings:
    host: str
    database: str
    username: str
    password: str
    port: int = 5432
    sslmode: str | None = None
    connect_timeout: int = 10

    @classmethod
    def from_env(cls, env_path: str = ".env") -> "PostgresSettings":
        _load_env_file(env_path)

        host = os.getenv("POSTGRES_HOST", "").strip()
        database = os.getenv("POSTGRES_DATABASE", "").strip()
        username = os.getenv("POSTGRES_USERNAME", "").strip()
        password = os.getenv("POSTGRES_PASSWORD", "").strip()

        missing = [
            key
            for key, value in {
                "POSTGRES_HOST": host,
                "POSTGRES_DATABASE": database,
                "POSTGRES_USERNAME": username,
                "POSTGRES_PASSWORD": password,
            }.items()
            if not value
        ]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"Variaveis ausentes no .env: {joined}")

        port = int(os.getenv("POSTGRES_PORT", "5432"))
        sslmode = os.getenv("POSTGRES_SSLMODE", "").strip() or None
        connect_timeout = int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10"))

        return cls(
            host=host,
            database=database,
            username=username,
            password=password,
            port=port,
            sslmode=sslmode,
            connect_timeout=connect_timeout,
        )


@dataclass(slots=True)
class PostgresClient:
    settings: PostgresSettings | None = None
    env_path: str = ".env"

    def __post_init__(self) -> None:
        if self.settings is None:
            self.settings = PostgresSettings.from_env(self.env_path)

    def _build_connection_kwargs(self) -> dict[str, Any]:
        if self.settings is None:
            raise RuntimeError("configuracao do Postgres nao inicializada")

        connection_kwargs: dict[str, Any] = {
            "host": self.settings.host,
            "dbname": self.settings.database,
            "user": self.settings.username,
            "password": self.settings.password,
            "port": self.settings.port,
            "connect_timeout": self.settings.connect_timeout,
        }
        if self.settings.sslmode:
            connection_kwargs["sslmode"] = self.settings.sslmode
        return connection_kwargs

    def execute(
        self,
        query: str,
        params: tuple[Any, ...] | list[Any] | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("query nao pode ser vazia")

        psycopg = _import_psycopg()
        with psycopg.connect(**self._build_connection_kwargs()) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)

                description = cursor.description
                if description:
                    columns = [column.name for column in description]
                    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    return {
                        "rowcount": cursor.rowcount,
                        "rows": rows,
                    }

                return {
                    "rowcount": cursor.rowcount,
                    "rows": [],
                }
