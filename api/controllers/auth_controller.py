from fastapi import APIRouter, HTTPException, Request, status

from api.schemas.auth_schema import LoginRequest, RotateTokenResponse, TokenResponse
from api.schemas.user_schema import RegisterRequest, UserResponse
from api.services.auth_service import AuthService
from api.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_auth_service(request: Request) -> AuthService:
    user_service = UserService(request.app.state.db)
    return AuthService(user_service)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request) -> UserResponse:
    service = _build_auth_service(request)
    return service.register(nome=payload.nome, email=payload.email, senha=payload.senha)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    service = _build_auth_service(request)
    token, user = service.login(email=payload.email, senha=payload.senha)
    return TokenResponse(token=token, usuario=user)


@router.post("/rotate-token", response_model=RotateTokenResponse)
def rotate_token(request: Request) -> RotateTokenResponse:
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autenticado")

    service = _build_auth_service(request)
    token = service.rotate_token(user_id=request.state.user.id)
    return RotateTokenResponse(token=token)


@router.get("/me", response_model=UserResponse)
def me(request: Request) -> UserResponse:
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nao autenticado")

    user = request.state.user
    return UserResponse(
        id=user.id,
        created_at=user.created_at,
        nome=user.nome,
        email=user.email,
        role=user.role,
    )
