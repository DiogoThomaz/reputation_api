from __future__ import annotations

from reputation_worker.interfaces import Scraper
from reputation_worker.scrapers.playstore import PlayStoreScraper
from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper


class ScraperFactory:
    """Seleciona o scraper correto por source."""

    _registry = {
        "playstore": PlayStoreScraper,
        "reclame_aqui": ReclameAquiScraper,
    }

    @classmethod
    def create(cls, source: str) -> Scraper:
        source_normalized = source.strip().lower()
        scraper_cls = cls._registry.get(source_normalized)
        if scraper_cls is None:
            supported = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"source invalido: {source}. Use um dos seguintes: {supported}"
            )
        return scraper_cls()
