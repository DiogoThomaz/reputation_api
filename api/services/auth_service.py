from __future__ import annotations

from fastapi import HTTPException, status

from api.models import UserModel
from api.schemas.user_schema import UserResponse
from api.services.password_service import PasswordService
from api.services.token_service import TokenService
from api.services.user_service import UserService


DEFAULT_ROLE = "USUARIO_PLANO_TESTE"


class AuthService:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    def register(self, nome: str, email: str, senha: str) -> UserResponse:
        existing_user = self.user_service.get_user_by_email(email)
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email ja cadastrado",
            )

        senha_hash = PasswordService.hash_password(senha)
        user = self.user_service.create_user(nome=nome, email=email, senha_hash=senha_hash, role=DEFAULT_ROLE)
        return self._to_user_response(user)

    def login(self, email: str, senha: str) -> tuple[str, UserResponse]:
        user = self.user_service.get_user_by_email(email)
        if user is None or not PasswordService.verify_password(senha, user.senha):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciais invalidas",
            )

        token = TokenService.generate_token()
        updated_user = self.user_service.update_token(user.id, token)
        return token, self._to_user_response(updated_user)

    def rotate_token(self, user_id: int) -> str:
        token = TokenService.generate_token()
        self.user_service.update_token(user_id, token)
        return token

    @staticmethod
    def _to_user_response(user: UserModel) -> UserResponse:
        return UserResponse(
            id=user.id,
            created_at=user.created_at,
            nome=user.nome,
            email=user.email,
            role=user.role,
        )
