from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class UserModel:
    id: int
    created_at: datetime
    nome: str
    email: str
    senha: str
    token: str | None
    role: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "UserModel":
        return cls(
            id=row["id"],
            created_at=row["created_at"],
            nome=row["nome"],
            email=row["email"],
            senha=row.get("senha") or "",
            token=row.get("token"),
            role=row["role"],
        )
