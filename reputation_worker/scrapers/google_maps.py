from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncGenerator, Dict, List, Optional

from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoogleMapsScrapper:
    """Scraper declarativo para Google Maps com persistencia incremental."""

    def __init__(
        self,
        empresas: List[str],
        cidades: List[str],
        headless: bool = True,
    ):
        self.empresas = [s.strip() for s in empresas if s and s.strip()]
        self.cidades = [c.strip() for c in cidades if c and c.strip()]
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None

    async def iniciar(self) -> None:
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(10000)

    async def fechar(self) -> None:
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def coletar(self) -> AsyncGenerator[Dict[str, str], None]:
        """Executa a coleta por setor/cidade e salva cada registro imediatamente."""
        if not self.empresas:
            raise ValueError("Lista de empresas vazia")
        if not self.cidades:
            raise ValueError("Lista de cidades vazia")

        await self.iniciar()

        try:
            for empresa in self.empresas:
                for cidade in self.cidades:
                    try:
                        async for record in self._coletar_setor_cidade(empresa, cidade):
                            yield record
                    except Exception as exc:
                        logger.error(f"Erro ao coletar setor/cidade: {exc}")
        finally:
            await self.fechar()

    async def _aguardar_cards_resultado(self):
        seletores = [
            'div[role="feed"] a[href*="/maps/place"]',
            'div[role="feed"] div[role="article"]',
            'a[href*="/maps/place"]',
        ]

        for seletor in seletores:
            locator = self.page.locator(seletor)
            try:
                await locator.first.wait_for(state="visible", timeout=12000)
                if await locator.count() > 0:
                    return locator
            except Exception:
                continue

        raise TimeoutError("Nao foi possivel localizar a lista de resultados no Google Maps")

    async def _obter_painel_resultados(self):
        seletores = [
            'div[role="feed"]',
            'div.m6QErb[role="feed"]',
            'div[aria-label*="Resultados"] div[role="feed"]',
        ]

        for seletor in seletores:
            painel = self.page.locator(seletor)
            try:
                await painel.first.wait_for(state="visible", timeout=8000)
                if await painel.count() > 0:
                    return painel.first
            except Exception:
                continue

        raise TimeoutError("Nao foi possivel localizar o painel de resultados")

    async def _carregar_mais_resultados_por_rolagem(self, cards_locator):
        painel = await self._obter_painel_resultados()

        ultimo_total = 0
        tentativas_sem_novos = 0

        for _ in range(80):
            total_atual = await cards_locator.count()
            if total_atual > ultimo_total:
                ultimo_total = total_atual
                tentativas_sem_novos = 0
            else:
                tentativas_sem_novos += 1

            if tentativas_sem_novos >= 5:
                break

            await painel.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            await self.page.wait_for_timeout(1400)

    async def _coletar_setor_cidade(
        self, setor: str, cidade: str
    ) -> AsyncGenerator[Dict[str, str], None]:
        url = f"https://www.google.com/maps/search/{setor},+{cidade}/"
        logger.info(f"Acessando: {url}")

        await self.page.goto(url)
        await self.page.wait_for_load_state("domcontentloaded")

        cards_locator = await self._aguardar_cards_resultado()
        await self._carregar_mais_resultados_por_rolagem(cards_locator)

        total_cards = await cards_locator.count()
        if total_cards == 0:
            logger.warning(f"Sem resultados para setor={setor} cidade={cidade}")
            return

        logger.info(f"Encontrados {total_cards} resultados para setor={setor} cidade={cidade}")

        for idx in range(total_cards):
            try:
                card = cards_locator.nth(idx)
                await card.scroll_into_view_if_needed()
                await card.click()
                await self.page.wait_for_timeout(1200)

                dados = await self._extrair_dados()
                if not any(dados.values()):
                    continue

                dados["setor"] = setor
                dados["cidade"] = cidade

                if dados:
                    yield dados

            except Exception as exc:
                logger.error(f"Erro ao processar card {idx + 1}/{total_cards}: {exc}")

    async def _extrair_dados(self) -> Dict[str, str]:
        dados = {
            "nome": "",
            "telefone": "",
            "email": "",
            "endereco": "",
            "site": "",
        }

        try:
            await self.page.wait_for_selector(
                'h1, [data-item-id="address"], [data-item-id^="phone"]', timeout=8000
            )

            dados["nome"] = await self._extrair_nome_negocio()

            dados["telefone"] = await self._texto_por_seletor('[data-item-id^="phone"]')
            dados["endereco"] = await self._texto_por_seletor('[data-item-id="address"]')

            site_element = self.page.locator('[data-item-id="authority"] a, a[data-item-id="authority"]')
            if await site_element.count() > 0:
                dados["site"] = (await site_element.first.get_attribute("href") or "").strip()

            if not any([dados["telefone"], dados["email"], dados["endereco"], dados["site"]]):
                await self._extrair_info_fallback(dados)
            else:
                await self._extrair_email(dados)

        except Exception as exc:
            logger.error(f"Erro ao extrair dados: {exc}")

        return dados

    async def _extrair_nome_negocio(self) -> str:
        # Prioriza o painel de detalhe do estabelecimento e ignora titulos genericos da busca.
        seletores = [
            'div[role="main"] h1.DUwDvf',
            'div[role="main"] h1.fontHeadlineLarge',
            'h1.DUwDvf',
            'h1.fontHeadlineLarge',
            'h1',
        ]

        for seletor in seletores:
            try:
                locator = self.page.locator(seletor)
                if await locator.count() == 0:
                    continue

                texto = (await locator.first.inner_text() or "").strip()
                if self._nome_valido(texto):
                    return texto
            except Exception:
                continue

        return ""

    @staticmethod
    def _nome_valido(nome: str) -> bool:
        if not nome:
            return False

        nome_normalizado = nome.strip().lower()
        invalidos = {
            "resultados",
            "results",
            "google maps",
            "maps",
        }

        if nome_normalizado in invalidos:
            return False

        if nome_normalizado.startswith("resultados"):
            return False

        return len(nome_normalizado) > 2

    async def _texto_por_seletor(self, seletor: str) -> str:
        try:
            locator = self.page.locator(seletor)
            if await locator.count() == 0:
                return ""

            texto = await locator.first.inner_text()
            return texto.strip() if texto else ""
        except Exception:
            return ""

    async def _extrair_email(self, dados: Dict[str, str]) -> None:
        try:
            page_text = await self.page.text_content("body")
            if not page_text:
                return

            email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
            if email_match:
                dados["email"] = email_match.group()
        except Exception:
            return

    async def _extrair_info_fallback(self, dados: Dict[str, str]) -> None:
        try:
            page_text = await self.page.text_content("body")
            if not page_text:
                return

            telefone_match = re.search(r"\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}", page_text)
            if telefone_match:
                dados["telefone"] = telefone_match.group()

            email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", page_text)
            if email_match:
                dados["email"] = email_match.group()

            site_match = re.search(r"https?://[^\s]+|www\.[^\s]+", page_text)
            if site_match:
                dados["site"] = site_match.group()
        except Exception:
            return



GoogleMapsScraper = GoogleMapsScrapper