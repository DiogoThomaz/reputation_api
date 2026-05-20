from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    telefone: str = Field(pattern=r"^\d{10,11}$")
    senha: str = Field(min_length=8, max_length=255)


class UserResponse(BaseModel):
    id: int
    created_at: datetime
    nome: str
    email: str
    role: str
