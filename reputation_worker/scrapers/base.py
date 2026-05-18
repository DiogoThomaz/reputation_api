from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol


Record = dict[str, Any]


class BaseScraper(Protocol):
    def scrape(self, query: str) -> Iterable[Record]:
        ...
