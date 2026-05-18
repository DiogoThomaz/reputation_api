import unittest
from datetime import datetime
from unittest.mock import patch

from reputation_worker.scrapers.playstore import PlayStoreScraper


FAKE_REVIEWS = [
    {
        "content": "Muito bom",
        "at": datetime(2026, 4, 15),
        "score": 5,
    },
    {
        "content": "Pode melhorar",
        "at": datetime(2026, 4, 16),
        "score": 3,
    },
]


class TestPlayStoreScraper(unittest.TestCase):
    @patch("reputation_worker.scrapers.playstore.reviews", return_value=(FAKE_REVIEWS, None))
    def test_scrape_returns_records(self, _mock):
        scraper = PlayStoreScraper()
        records = list(scraper.scrape("com.exemplo.app"))

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["review"], "Muito bom")
        self.assertEqual(records[0]["quantidade_estrelas"], "5")

    @patch("reputation_worker.scrapers.playstore.reviews", return_value=(FAKE_REVIEWS, None))
    def test_scrape_passes_correct_params(self, mock_reviews):
        scraper = PlayStoreScraper(lang="en", country="us", count=50)
        list(scraper.scrape("com.exemplo.app"))

        mock_reviews.assert_called_once_with(
            "com.exemplo.app",
            lang="en",
            country="us",
            sort=scraper.sort,
            count=50,
        )


if __name__ == "__main__":
    unittest.main()
