import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from api.controllers import collect_router
from api.middlewares import AccessLogMiddleware
from reputation_worker.collector import CollectJobManager
from reputation_worker.postgres import PostgresClient

app = FastAPI()
app.add_middleware(AccessLogMiddleware)
app.include_router(collect_router)
app.state.db = PostgresClient()
app.state.collect = CollectJobManager(app.state.db)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "frontend" / "index.html")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}


main = app


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)