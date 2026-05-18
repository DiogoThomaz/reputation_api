import unittest

from reputation_worker.scrapers.factory import ScraperFactory
from reputation_worker.scrapers.playstore import PlayStoreScraper
from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper


class TestScraperFactory(unittest.TestCase):
    def test_create_playstore(self):
        scraper = ScraperFactory.create("playstore")
        self.assertIsInstance(scraper, PlayStoreScraper)

    def test_create_reclame_aqui(self):
        scraper = ScraperFactory.create("reclame_aqui")
        self.assertIsInstance(scraper, ReclameAquiScraper)

    def test_invalid_source_raises(self):
        with self.assertRaises(ValueError):
            ScraperFactory.create("fonte_inexistente")


if __name__ == "__main__":
    unittest.main()
