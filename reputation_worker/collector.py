"""Orquestra a coleta de reviews da Play Store: resolve app_id, coleta,
avalia (sentimento/intencoes) e persiste em reviews_v1 com dedupe.

Cada job coleta em background e emite eventos (dict) para uma fila,
consumida pelo endpoint SSE.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from queue import Queue
from typing import Any

import requests
from google_play_scraper import search

from reputation_worker.analysis.analyzer import ReviewAnalyzer
from reputation_worker.postgres import PostgresClient
from reputation_worker.scrapers.playstore import PlayStoreScraper

logger = logging.getLogger(__name__)

DEDUPE_QUERY = (
    "SELECT 1 FROM reviews_v1 WHERE source = %s AND external_id = %s AND empresa = %s"
)
INSERT_QUERY = (
    "INSERT INTO reviews_v1 "
    "(source, empresa, data, review, quantidade_estrelas, external_id, sentimento, intencoes) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)"
)


def _search_raw_ids(termo: str, timeout: float = 10.0) -> list[str]:
    """Fallback: extrai os package ids do HTML da busca oficial da Play Store.

    A lib google-play-scraper nao extrai o appId do card em destaque da busca;
    aqui lemos o HTML direto, onde o primeiro link details?id= e o topo da busca.
    """
    response = requests.get(
        "https://play.google.com/store/search",
        params={"q": termo, "c": "apps", "hl": "pt_BR", "gl": "br"},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return re.findall(r"/store/apps/details\?id=([a-zA-Z0-9_.]+)", response.text)


def resolve_app_id(
    termo: str,
    search_fn: Any = search,
    raw_fn: Any = _search_raw_ids,
) -> str:
    """Nome do app -> package id (via busca na Play Store).

    Se o termo ja parece um package id (contem ponto e sem espacos), usa direto.
    De outra forma: prefere o resultado cujo titulo contenha o termo; se o card
    do topo vier sem appId (limitacao da lib), resolve pelo HTML oficial.
    """
    termo = (termo or "").strip()
    if not termo:
        raise ValueError("informe o nome do aplicativo")
    if "." in termo and " " not in termo:
        return termo

    termo_norm = termo.lower()
    results = search_fn(termo, lang="pt", country="br", n_hits=10)
    fallback = ""
    for item in results or []:
        app_id = item.get("appId")
        title = str(item.get("title") or "").lower()
        if app_id:
            fallback = str(app_id)
            if termo_norm in title:
                return fallback
        elif termo_norm in title:
            # card do topo sem appId: nao retorna aqui, deixa o fallback bruto decidir
            raw_ids = raw_fn(termo)
            if raw_ids:
                return raw_ids[0]
    if fallback:
        return fallback
    raw_ids = raw_fn(termo)
    if raw_ids:
        return raw_ids[0]
    raise ValueError(f"nenhum aplicativo encontrado para: {termo}")


@dataclass(slots=True)
class CollectJob:
    termo: str
    count: int
    queue: Queue = field(default_factory=Queue)
    status: str = "queued"  # queued | running | done | error
    app_id: str = ""
    error: str = ""


class PlayStoreCollector:
    """Executa um CollectJob: coleta, avalia e persiste, emitindo eventos."""

    def __init__(
        self,
        db: Any,
        analyzer: Any = None,
        scraper_cls: type = PlayStoreScraper,
        resolve_fn: Any = resolve_app_id,
    ) -> None:
        self.db = db
        self.analyzer = analyzer or ReviewAnalyzer()
        self.scraper_cls = scraper_cls
        self.resolve_fn = resolve_fn

    def _check_exists(self, source: str, external_id: str, empresa: str) -> bool:
        result = self.db.execute(DEDUPE_QUERY, (source, external_id, empresa))
        return result["rowcount"] > 0

    def run(self, job: CollectJob) -> dict[str, Any]:
        job.status = "running"
        resumo = {
            "coletadas": 0,
            "avaliadas": 0,
            "inseridas": 0,
            "puladas": 0,
            "erros": 0,
            "positivos": 0,
            "negativos": 0,
            "neutros": 0,
            "intencoes": {},
        }
        try:
            job.app_id = self.resolve_fn(job.termo)
            job.queue.put({"type": "start", "app_id": job.app_id, "termo": job.termo, "count": job.count})

            scraper = self.scraper_cls(count=job.count)
            for review in scraper.scrape(job.app_id):
                resumo["coletadas"] += 1
                sentimento = "neutro"
                intencoes: list[str] = []
                inserido = False
                try:
                    avaliacao = self.analyzer.analyze(review["review"], review.get("quantidade_estrelas"))
                    sentimento = avaliacao["sentimento"]
                    intencoes = avaliacao["intencoes"]
                    resumo["avaliadas"] += 1
                    resumo[sentimento + "s"] += 1  # positivos/negativos/neutros
                    for intent in intencoes:
                        resumo["intencoes"][intent] = resumo["intencoes"].get(intent, 0) + 1

                    if self._check_exists("playstore", review["id"], job.termo):
                        resumo["puladas"] += 1
                    else:
                        self.db.execute(
                            INSERT_QUERY,
                            (
                                "playstore",
                                job.termo,
                                review["data"],
                                review["review"],
                                review["quantidade_estrelas"],
                                review["id"],
                                sentimento,
                                json.dumps(intencoes, ensure_ascii=False),
                            ),
                        )
                        resumo["inseridas"] += 1
                        inserido = True
                except Exception:
                    logger.exception("Erro ao avaliar/persistir review | app=%s", job.app_id)
                    resumo["erros"] += 1

                job.queue.put(
                    {
                        "type": "review",
                        "review": review,
                        "sentimento": sentimento,
                        "intencoes": intencoes,
                        "inserido": inserido,
                        "progresso": {"coletadas": resumo["coletadas"], "avaliadas": resumo["avaliadas"]},
                    }
                )
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            job.queue.put({"type": "error", "message": str(exc)})
            logger.exception("Job falhou | termo=%s", job.termo)
            return resumo

        job.status = "done"
        job.queue.put({"type": "done", "resumo": resumo})
        logger.info("Job concluido | termo=%s resumo=%s", job.termo, json.dumps(resumo, ensure_ascii=False))
        return resumo


class CollectJobManager:
    """Registra jobs, roda cada um em thread daemon e serve a fila de eventos."""

    def __init__(self, db: PostgresClient) -> None:
        self.db = db
        self.jobs: dict[str, CollectJob] = {}

    def start(self, termo: str, count: int = 100) -> str:
        job_id = uuid.uuid4().hex[:12]
        job = CollectJob(termo=termo, count=count)
        self.jobs[job_id] = job

        collector = PlayStoreCollector(self.db)
        thread = threading.Thread(target=collector.run, args=(job,), daemon=True)
        thread.start()
        return job_id

    def get(self, job_id: str) -> CollectJob | None:
        return self.jobs.get(job_id)

    def stream_events(self, job_id: str):
        """Itera sobre os eventos do job; termina quando o worker sinaliza None."""
        job = self.jobs.get(job_id)
        if job is None:
            yield {"type": "error", "message": "job nao encontrado"}
            return
        while True:
            event = job.queue.get()
            if event is None:
                return
            yield event