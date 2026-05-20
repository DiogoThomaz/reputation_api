import logging
import os

import uvicorn
from fastapi import FastAPI

from api.controllers import auth_router
from api.middlewares import AuthMiddleware
from reputation_worker.postgres import PostgresClient

app = FastAPI()
app.add_middleware(AuthMiddleware)
app.include_router(auth_router)
app.state.db = PostgresClient()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


main = app
