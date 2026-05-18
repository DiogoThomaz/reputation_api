from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from reputation_worker.interfaces import BatchCallback, Scraper
from reputation_worker.scrapers.factory import ScraperFactory

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ScraperWorker:
    """Orquestra scraping e envio em lotes para callback externo."""

    source: str
    chunk_yield: int
    callback: BatchCallback
    scraper: Scraper | None = field(default=None)

    def __post_init__(self) -> None:
        if self.chunk_yield <= 0:
            raise ValueError("chunk_yield deve ser maior que zero")
        if self.scraper is None:
            self.scraper = ScraperFactory.create(self.source)

    def run(self, source_input: str) -> int:
        if self.scraper is None:
            raise RuntimeError("scraper nao inicializado")

        logger.info("Iniciando worker | source=%s input=%s chunk_yield=%d", self.source, source_input, self.chunk_yield)

        total = 0
        batch: list[dict[str, Any]] = []

        for item in self.scraper.scrape(source_input):
            batch.append(item)
            total += 1
            if len(batch) >= self.chunk_yield:
                logger.info("Enviando lote | registros=%d total_acumulado=%d", len(batch), total)
                self.callback(batch.copy())
                batch.clear()

        if batch:
            logger.info("Enviando lote final | registros=%d total_acumulado=%d", len(batch), total)
            self.callback(batch.copy())

        logger.info("Worker concluido | source=%s input=%s total_registros=%d", self.source, source_input, total)
        return total


# Planejamento futuro:
# esta interface permitira anexar o worker a uma fila RabbitMQ sem mudar a regra
# de chunk/callback ja testada.
class QueueDispatcher:
    def publish(self, queue_name: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError
