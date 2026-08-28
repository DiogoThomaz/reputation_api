import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from reputation_worker.collector import CollectJobManager


class CollectRequest(BaseModel):
    app_id: str = Field(min_length=2, description="Nome do app ou package id da Play Store")
    count: int = Field(default=100, ge=1, le=500)


router = APIRouter(tags=["collect"])


def _manager(request: Request) -> CollectJobManager:
    return request.app.state.collect


@router.post("/collect", status_code=status.HTTP_202_ACCEPTED)
def collect(payload: CollectRequest, request: Request) -> dict[str, str]:
    job_id = _manager(request).start(termo=payload.app_id, count=payload.count)
    return {"job_id": job_id}


@router.get("/stream/{job_id}")
def stream(job_id: str, request: Request) -> StreamingResponse:
    if _manager(request).get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job nao encontrado")

    def event_stream():
        for event in _manager(request).stream_events(job_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/recent")
def recent(request: Request, limit: int = 50) -> dict[str, Any]:
    """Ultimas reviews coletadas (para popular a tela ao abrir)."""
    limit = max(1, min(limit, 200))
    result = _manager(request).db.execute(
        (
            "SELECT id, empresa, review, quantidade_estrelas, sentimento, intencoes, data "
            "FROM reviews_v1 ORDER BY id DESC LIMIT %s"
        ),
        (limit,),
    )
    return {"rows": result["rows"]}