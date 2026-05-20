import logging
import os

from fastapi import FastAPI

from api.controllers import auth_router
from api.middlewares import AuthMiddleware
from reputation_worker.postgres import PostgresClient


def create_app() -> FastAPI:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )

    app = FastAPI(title="Auth API", version="1.0.0")
    app.state.db = PostgresClient()
    app.add_middleware(AuthMiddleware)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth_router)
    return app


app = create_app()
