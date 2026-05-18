from __future__ import annotations

from collections.abc import Generator

from google_play_scraper import reviews, Sort

Record = dict[str, str]


class PlayStoreScraper:
    """Scraper de reviews da Play Store usando google-play-scraper."""

    def __init__(
        self,
        lang: str = "pt",
        country: str = "br",
        sort: Sort = Sort.NEWEST,
        count: int = 500,
    ) -> None:
        self.lang = lang
        self.country = country
        self.sort = sort
        self.count = count

    def scrape(self, app_id: str) -> Generator[Record, None, None]:
        result, _ = reviews(
            app_id,
            lang=self.lang,
            country=self.country,
            sort=self.sort,
            count=self.count,
        )
        for item in result:
            print(item)
            yield {
                "review": str(item.get("content") or "").strip(),
                "data": str(item.get("at") or "").strip(),
                "quantidade_estrelas": str(item.get("score") or "").strip(),
                "usuario": str(item.get("userName") or "").strip(),
                "id": str(item.get("reviewId") or "").strip(),
            }

