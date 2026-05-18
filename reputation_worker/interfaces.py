from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


Record = dict[str, Any]


class Scraper(Protocol):
    """Contrato comum para scrapers de fontes diferentes."""

    def scrape(self, query: str) -> Iterable[Record]:
        ...


class BatchCallback(Protocol):
    """Callback externo para envio dos dados processados."""

    def __call__(self, records: list[Record]) -> None:
        ...
