import unittest
from unittest.mock import patch

import main_postgres


class FakeDb:
    def __init__(self):
        self.playstore_exists_checks = 0
        self.playstore_insert_sizes = []
        self.reclame_exists_checks = 0
        self.reclame_insert_sizes = []

    def execute(self, query, params=None):
        lowered = query.lower()

        if lowered.startswith("select * from empresa"):
            return {
                "rowcount": 1,
                "rows": [
                    {
                        "nome": "Empresa X",
                        "playstore_id": "app.id.x",
                        "reclame_aqui_id": "empresa-x",
                    }
                ],
            }

        if lowered.startswith("select external_id from reviews_v1"):
            source = params[0]
            total_ids = len(params) - 2
            if source == "playstore":
                self.playstore_exists_checks += 1
            if source == "reclame_aqui":
                self.reclame_exists_checks += 1
            return {"rowcount": 0, "rows": []}

        if lowered.startswith("insert into reviews_v1"):
            if "quantidade_estrelas" in lowered:
                rows = len(params) // 6
                self.playstore_insert_sizes.append(rows)
                return {"rowcount": rows, "rows": []}

            rows = len(params) // 7
            self.reclame_insert_sizes.append(rows)
            return {"rowcount": rows, "rows": []}

        raise AssertionError(f"Query inesperada: {query}")


class TestMainPostgresBatch(unittest.TestCase):
    @patch("main_postgres.PlayStoreScraper")
    def test_playstore_checks_and_inserts_in_batches_of_50(self, mock_scraper_cls):
        fake_reviews = [
            {
                "id": str(index),
                "data": "2026-01-01",
                "review": "texto",
                "quantidade_estrelas": 5,
            }
            for index in range(120)
        ]

        mock_scraper = mock_scraper_cls.return_value
        mock_scraper.scrape.return_value = iter(fake_reviews)

        fake_db = FakeDb()

        main_postgres.run_playstore(db=fake_db)

        self.assertEqual(fake_db.playstore_exists_checks, 3)
        self.assertEqual(fake_db.playstore_insert_sizes, [50, 50, 20])

    @patch("main_postgres.ReclameAquiScraper")
    def test_reclame_checks_and_inserts_in_batches_of_50(self, mock_scraper_cls):
        fake_reviews = [
            {
                "id": str(index),
                "data": "2026-01-01",
                "reclamacao": "texto",
                "titulo": "titulo",
                "local": "SP",
            }
            for index in range(120)
        ]

        mock_context = mock_scraper_cls.return_value.__enter__.return_value
        mock_context.scrape.return_value = iter(fake_reviews)

        fake_db = FakeDb()

        main_postgres.run_reclame_aqui(db=fake_db)

        self.assertEqual(fake_db.reclame_exists_checks, 3)
        self.assertEqual(fake_db.reclame_insert_sizes, [50, 50, 20])


if __name__ == "__main__":
    unittest.main()
