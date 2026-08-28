import unittest
from queue import Queue
from typing import Any

from reputation_worker.collector import CollectJob, PlayStoreCollector, resolve_app_id


class FakeDB:
    def __init__(self, existe: bool = False):
        self.calls: list[tuple[str, Any]] = []
        self.existe = existe

    def execute(self, query: str, params=None):
        self.calls.append((query, params))
        if query.startswith("SELECT 1"):
            return {"rowcount": 1 if self.existe else 0, "rows": []}
        return {"rowcount": 1, "rows": []}


REVIEWS = [
    {"review": "Ótimo app!", "data": "2026-01-01", "quantidade_estrelas": "5", "id": "r1", "usuario": "u1"},
    {"review": "Péssimo, não funciona", "data": "2026-01-02", "quantidade_estrelas": "1", "id": "r2", "usuario": "u2"},
]


class FakeScraper:
    def __init__(self, count: int = 100):
        self.count = count

    def scrape(self, app_id: str):
        yield from REVIEWS


class FakeAnalyzer:
    def analyze(self, review: str, estrelas=None):
        if "Ótimo" in review:
            return {"sentimento": "positivo", "intencoes": ["elogio"]}
        return {"sentimento": "negativo", "intencoes": ["problema_tecnico"]}


class TestResolveAppId(unittest.TestCase):
    def test_package_id_passado_direto(self):
        self.assertEqual(resolve_app_id("com.nubank.celular"), "com.nubank.celular")

    def test_nome_resolve_via_search(self):
        results = [{"appId": "com.nubank.celular", "title": "Nubank - Conta"}]
        self.assertEqual(resolve_app_id("nubank", search_fn=lambda *a, **k: results), "com.nubank.celular")

    def test_nome_prefere_titulo_com_termo(self):
        # busca desordenada: titulo com o termo deve vencer
        results = [
            {"appId": "com.mercadopago.wallet", "title": "Mercado Pago"},
            {"appId": "com.nubank.celular", "title": "Nubank - Conta"},
        ]
        self.assertEqual(resolve_app_id("nubank", search_fn=lambda *a, **k: results), "com.nubank.celular")

    def test_card_do_topo_sem_appid_usar_raw(self):
        # card do topo (relevante) sem appId: resolve pelo HTML oficial
        results = [
            {"appId": None, "title": "Nubank: conta, cartão e mais"},
            {"appId": "com.mercadopago.wallet", "title": "Mercado Pago: Banco Digital"},
        ]
        self.assertEqual(
            resolve_app_id(
                "nubank",
                search_fn=lambda *a, **k: results,
                raw_fn=lambda termo: ["com.nubank.celular", "com.mercadopago.wallet"],
            ),
            "com.nubank.celular",
        )

    def test_sem_resultado_levanta_erro(self):
        with self.assertRaises(ValueError):
            resolve_app_id("app inexistente xyz", search_fn=lambda *a, **k: [], raw_fn=lambda termo: [])

    def test_termo_vazio_levanta_erro(self):
        with self.assertRaises(ValueError):
            resolve_app_id("   ")


class TestPlayStoreCollector(unittest.TestCase):
    def _drain(self, queue: Queue) -> list[dict]:
        events = []
        while not queue.empty():
            events.append(queue.get())
        return events

    def test_fluxo_completo(self):
        db = FakeDB()
        job = CollectJob(termo="nubank", count=100)
        collector = PlayStoreCollector(
            db=db,
            analyzer=FakeAnalyzer(),
            scraper_cls=FakeScraper,
            resolve_fn=lambda termo: "com.nubank.celular",
        )

        resumo = collector.run(job)

        self.assertEqual(job.status, "done")
        self.assertEqual(resumo["coletadas"], 2)
        self.assertEqual(resumo["avaliadas"], 2)
        self.assertEqual(resumo["inseridas"], 2)
        self.assertEqual(resumo["positivos"], 1)
        self.assertEqual(resumo["negativos"], 1)
        self.assertEqual(resumo["intencoes"]["elogio"], 1)
        self.assertEqual(resumo["intencoes"]["problema_tecnico"], 1)

        events = self._drain(job.queue)
        types = [event["type"] for event in events]
        self.assertEqual(types, ["start", "review", "review", "done"])
        # INSERT com intencoes como JSON string (coluna jsonb)
        inserts = [params for query, params in db.calls if query.startswith("INSERT")]
        self.assertEqual(len(inserts), 2)
        self.assertEqual(inserts[0][7], '["elogio"]')
        self.assertEqual(inserts[1][7], '["problema_tecnico"]')

    def test_dedupe_pula_reviews_existentes(self):
        db = FakeDB(existe=True)
        job = CollectJob(termo="nubank", count=100)
        collector = PlayStoreCollector(
            db=db,
            analyzer=FakeAnalyzer(),
            scraper_cls=FakeScraper,
            resolve_fn=lambda termo: "com.nubank.celular",
        )

        resumo = collector.run(job)

        self.assertEqual(resumo["puladas"], 2)
        self.assertEqual(resumo["inseridas"], 0)
        self.assertEqual(len([c for c in db.calls if c[0].startswith("INSERT")]), 0)

    def test_erro_de_analise_nao_derruba_job(self):
        class AnalyzerQuebrado:
            def analyze(self, review, estrelas=None):
                raise RuntimeError("ollama fora")

        db = FakeDB()
        job = CollectJob(termo="nubank", count=100)
        collector = PlayStoreCollector(
            db=db,
            analyzer=AnalyzerQuebrado(),
            scraper_cls=FakeScraper,
            resolve_fn=lambda termo: "com.nubank.celular",
        )

        resumo = collector.run(job)

        self.assertEqual(job.status, "done")
        self.assertEqual(resumo["erros"], 2)
        events = self._drain(job.queue)
        self.assertEqual([e["type"] for e in events], ["start", "review", "review", "done"])
        # evento com fallback neutro
        review_events = [e for e in events if e["type"] == "review"]
        self.assertEqual(review_events[0]["sentimento"], "neutro")

    def test_erro_de_resolucao_marca_job_como_error(self):
        db = FakeDB()
        job = CollectJob(termo="app inexistente xyz", count=100)
        collector = PlayStoreCollector(
            db=db,
            analyzer=FakeAnalyzer(),
            scraper_cls=FakeScraper,
            resolve_fn=lambda termo: (_ for _ in ()).throw(ValueError("nenhum app")),
        )

        collector.run(job)

        self.assertEqual(job.status, "error")
        events = self._drain(job.queue)
        self.assertEqual([e["type"] for e in events], ["error"])


if __name__ == "__main__":
    unittest.main()