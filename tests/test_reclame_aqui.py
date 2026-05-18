import unittest

from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper


LISTING_HTML = """
<html><head></head><body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "complaints": {
        "LAST": [
          {
            "id": "aaa1",
            "title": "Entrega atrasada",
            "description": "Meu pedido nao chegou",
            "created": "2026-04-01T10:00:00",
            "status": "ABERTA",
            "userName": "usuario1",
            "url": "/nubank/aaa1-entrega-atrasada/"
          },
          {
            "id": "aaa2",
            "title": "Produto com defeito",
            "description": "Quebrou em dois dias",
            "created": "2026-04-02T11:00:00",
            "status": "RESOLVIDA",
            "userName": "usuario2",
            "url": "/nubank/aaa2-produto-com-defeito/"
          }
        ],
        "count": 2
      }
    }
  }
}
</script>
</body></html>
"""

EMPTY_LISTING_HTML = """
<html><head></head><body>
<script id="__NEXT_DATA__" type="application/json">
{"props": {"pageProps": {"complaints": {"LAST": [], "count": 0}}}}
</script>
</body></html>
"""


class TestReclameAquiScraper(unittest.TestCase):
    def test_accesses_each_link_and_extracts_detail_fields(self):
        """Deve entrar no link da reclamacao e extrair os campos do detalhe."""
        detail_1 = """
        <html><body><script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "complaint": {
                "id": "1opBzW5WBhp08SSI",
                "title": "Nao recebimento do certificado",
                "description": "Boa noite, meu nome e Valeria.",
                "location": "Pocos de Caldas - MG",
                "createdAt": "29/04/2026 as 20:46",
                "status": "NAO_RESPONDIDA"
              }
            }
          }
        }
        </script></body></html>
        """

        detail_2 = """
        <html><body><script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "complaint": {
                "id": "XYZ123",
                "title": "Produto com defeito",
                "description": "Quebrou em dois dias",
                "city": "Sao Paulo",
                "state": "SP",
                "created": "2026-04-02T11:00:00",
                "status": "RESPONDIDA"
              }
            }
          }
        }
        </script></body></html>
        """

        def fetch(url: str) -> str:
            if "lista-reclamacoes" in url:
                return LISTING_HTML
            if "aaa1-entrega-atrasada" in url:
                return detail_1
            if "aaa2-produto-com-defeito" in url:
                return detail_2
            return EMPTY_LISTING_HTML

        scraper = ReclameAquiScraper(fetch_html=fetch, delay=0, max_pages=1)
        records = list(scraper.scrape("nubank"))

        self.assertEqual(len(records), 2)

        r = records[0]
        self.assertEqual(r["titulo"], "Nao recebimento do certificado")
        self.assertEqual(r["reclamacao"], "Boa noite, meu nome e Valeria.")
        self.assertEqual(r["local"], "Pocos de Caldas - MG")
        self.assertEqual(r["data"], "29/04/2026 as 20:46")
        self.assertEqual(r["id"], "1opBzW5WBhp08SSI")
        self.assertEqual(r["nome_empresa"], "nubank")
        self.assertEqual(r["status"], "NAO_RESPONDIDA")
        self.assertIn("aaa1-entrega-atrasada", r["link"])

        r2 = records[1]
        self.assertEqual(r2["local"], "Sao Paulo - SP")
        self.assertEqual(r2["id"], "XYZ123")

    def test_stops_when_listing_is_empty(self):
        """Deve parar de paginar quando LAST vier vazio."""
        def fetch(url: str) -> str:
            return EMPTY_LISTING_HTML

        scraper = ReclameAquiScraper(fetch_html=fetch, max_pages=10, delay=0)
        records = list(scraper.scrape("nubank"))
        self.assertEqual(records, [])

    def test_paginates_until_empty(self):
        """Deve coletar paginas ate encontrar listagem vazia."""
        listing_calls = {"n": 0}
        detail_html = """
        <html><body><script id="__NEXT_DATA__" type="application/json">
        {"props": {"pageProps": {"complaint": {
          "id": "abc",
          "title": "Titulo",
          "description": "Descricao",
          "location": "Cidade - UF",
          "createdAt": "2026-04-01",
          "status": "ABERTA"
        }}}}
        </script></body></html>
        """

        def fetch(url: str) -> str:
            if "lista-reclamacoes" in url:
                listing_calls["n"] += 1
                if listing_calls["n"] == 1:
                    return LISTING_HTML
                return EMPTY_LISTING_HTML
            return detail_html

        scraper = ReclameAquiScraper(fetch_html=fetch, max_pages=5, delay=0)
        records = list(scraper.scrape("nubank"))
        self.assertEqual(len(records), 2)
        self.assertEqual(listing_calls["n"], 2)


if __name__ == "__main__":
    unittest.main()
