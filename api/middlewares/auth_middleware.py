from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.services.user_service import UserService


PUBLIC_PATHS = {
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/auth/login",
    "/auth/register",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token ausente ou formato invalido"},
            )

        token = auth_header.replace("Bearer ", "", 1).strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token ausente ou formato invalido"},
            )

        user_service = UserService(request.app.state.db)
        user = user_service.get_user_by_token(token)
        if user is None:
            return JSONResponse(status_code=401, content={"detail": "Token invalido"})

        request.state.user = user
        return await call_next(request)
