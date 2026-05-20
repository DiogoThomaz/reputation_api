from pydantic import BaseModel, EmailStr, Field

from .user_schema import UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=8, max_length=255)


class TokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    usuario: UserResponse


class RotateTokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
