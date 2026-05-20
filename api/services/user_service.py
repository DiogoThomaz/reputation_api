from __future__ import annotations

from api.models import UserModel
from reputation_worker.postgres import PostgresClient


class UserService:
    def __init__(self, db: PostgresClient):
        self.db = db

    def get_user_by_email(self, email: str) -> UserModel | None:
        result = self.db.execute(
            query=(
                "SELECT id, created_at, nome, email, senha, token, role "
                "FROM usuarios "
                "WHERE email = %s"
            ),
            params=(email,),
        )
        if not result["rows"]:
            return None
        return UserModel.from_row(result["rows"][0])

    def get_user_by_token(self, token: str) -> UserModel | None:
        result = self.db.execute(
            query=(
                "SELECT id, created_at, nome, email, senha, token, role "
                "FROM usuarios "
                "WHERE token = %s"
            ),
            params=(token,),
        )
        if not result["rows"]:
            return None
        return UserModel.from_row(result["rows"][0])

    def create_user(self, nome: str, email: str, senha_hash: str, role: str) -> UserModel:
        result = self.db.execute(
            query=(
                "INSERT INTO usuarios (nome, email, senha, role) "
                "VALUES (%s, %s, %s, %s) "
                "RETURNING id, created_at, nome, email, senha, token, role"
            ),
            params=(nome, email, senha_hash, role),
        )
        return UserModel.from_row(result["rows"][0])

    def update_token(self, user_id: int, token: str) -> UserModel:
        result = self.db.execute(
            query=(
                "UPDATE usuarios "
                "SET token = %s "
                "WHERE id = %s "
                "RETURNING id, created_at, nome, email, senha, token, role"
            ),
            params=(token, user_id),
        )
        return UserModel.from_row(result["rows"][0])
