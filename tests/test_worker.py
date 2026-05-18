import unittest

from reputation_worker.worker import ScraperWorker


class DummyScraper:
    def __init__(self, rows):
        self.rows = rows

    def scrape(self, query):
        return iter(self.rows)


class TestWorker(unittest.TestCase):
    def test_yields_in_chunks_and_flushes_remaining(self):
        output = []
        rows = [
            {"id": 1},
            {"id": 2},
            {"id": 3},
            {"id": 4},
            {"id": 5},
        ]

        worker = ScraperWorker(
            source="playstore",
            chunk_yield=2,
            callback=lambda chunk: output.append(chunk),
            scraper=DummyScraper(rows),
        )

        total = worker.run("qualquer")

        self.assertEqual(total, 5)
        self.assertEqual(len(output), 3)
        self.assertEqual(output[0], [{"id": 1}, {"id": 2}])
        self.assertEqual(output[1], [{"id": 3}, {"id": 4}])
        self.assertEqual(output[2], [{"id": 5}])

    def test_invalid_chunk_raises(self):
        with self.assertRaises(ValueError):
            ScraperWorker(source="playstore", chunk_yield=0, callback=lambda _: None)


if __name__ == "__main__":
    unittest.main()
