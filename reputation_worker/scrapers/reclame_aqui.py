from __future__ import annotations

from datetime import datetime
import json
import logging
import random
import re
import time
from collections.abc import Callable, Generator
from html import unescape
from urllib.parse import quote, urljoin

from playwright.sync_api import sync_playwright, Page

logger = logging.getLogger(__name__)

Record = dict[str, str]
FetchFn = Callable[[str], str]

BASE_URL = "https://www.reclameaqui.com.br"

_BROWSER_ARGS = ["--disable-blink-features=AutomationControlled", "--no-sandbox"]
_USER_AGENTS = [
    # Chrome — Windows 10/11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Chrome — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Edge — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Firefox — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13.6; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Safari — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
]


class ReclameAquiScraper:
    """
    Scraper de reclamacoes por slug de empresa usando Playwright.

    Fluxo:
      1. Itera pelas paginas de listagem:
         /empresa/{slug}/lista-reclamacoes/?pagina={n}
        2. Extrai os links individuais da listagem (complaints.LAST[].url).
        3. Acessa cada link e extrai os dados da reclamacao no detalhe.
    """

    def __init__(
        self,
        fetch_html: FetchFn | None = None,
        max_pages: int = 5,
        delay: float = 4.0,
        listing_retries: int = 3,
        detail_retries: int = 3,
        max_empty_pages: int = 3,
        headless: bool = True,
    ) -> None:
        self._custom_fetch = fetch_html
        self._fetch: FetchFn = fetch_html or self._pw_fetch
        self.max_pages = max_pages
        self.delay = delay
        self.listing_retries = max(1, listing_retries)
        self.detail_retries = max(1, detail_retries)
        self.max_empty_pages = max(1, max_empty_pages)
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page: Page | None = None

    def __enter__(self) -> "ReclameAquiScraper":
        if self._custom_fetch is None:
            logger.info("Iniciando browser | headless=%s", self.headless)
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                args=_BROWSER_ARGS,
            )
            ctx = self._browser.new_context(
                user_agent=random.choice(_USER_AGENTS),
                locale="pt-BR",
                viewport={"width": 1280, "height": 900},
            )
            self._page = ctx.new_page()
            self._page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        return self

    def __exit__(self, *_) -> None:
        if self._page is not None:
            self._page.close()
        if self._browser is not None:
            self._browser.close()
            logger.info("Browser encerrado")
        if self._pw is not None:
            self._pw.stop()

    def scrape(self, nome_empresa: str) -> Generator[Record, None, None]:
        links = self._collect_listing_links(nome_empresa)
        total_links = len(links)
        logger.info(
            "Iniciando coleta de detalhes | empresa=%s total_links=%d",
            nome_empresa,
            total_links,
        )

        coletados = 0
        for idx, link in enumerate(links, start=1):
            detail_url = self._build_detail_url(link, nome_empresa)
            logger.info(
                "[%d/%d] Acessando detalhe | url=%s",
                idx,
                total_links,
                detail_url,
            )
            try:
                if self._custom_fetch is None:
                    record = None
                    for attempt in range(1, self.detail_retries + 1):
                        detail_html = self._pw_fetch_isolated(detail_url)
                        record = self._parse_detail(detail_html, nome_empresa, detail_url)
                        if record:
                            break
                        logger.warning(
                            "[%d/%d] Tentativa %d/%d sem dados | url=%s",
                            idx,
                            total_links,
                            attempt,
                            self.detail_retries,
                            detail_url,
                        )
                        if self.delay > 0:
                            time.sleep(self.delay)
                else:
                    detail_html = self._fetch(detail_url)
                    record = self._parse_detail(detail_html, nome_empresa, detail_url)
            except Exception as exc:
                logger.exception(
                    "[%d/%d] Erro ao acessar detalhe | url=%s erro=%s",
                    idx,
                    total_links,
                    detail_url,
                    exc,
                )
                record = None

            if record:
                coletados += 1
                logger.debug(
                    "[%d/%d] Registro extraido | id=%s titulo=%s",
                    idx,
                    total_links,
                    record.get("id", ""),
                    record.get("titulo", "")[:60],
                )
                yield record
            else:
                logger.warning(
                    "[%d/%d] Detalhe sem dados, ignorado | url=%s",
                    idx,
                    total_links,
                    detail_url,
                )

            if self.delay > 0:
                time.sleep(self.delay)

        logger.info(
            "Coleta de detalhes concluida | empresa=%s coletados=%d ignorados=%d",
            nome_empresa,
            coletados,
            total_links - coletados,
        )

    def _collect_listing_links(self, nome_empresa: str) -> list[str]:
        logger.info(
            "Iniciando coleta de listagem | empresa=%s max_pages=%s",
            nome_empresa,
            self.max_pages if self.max_pages > 0 else "ilimitado",
        )
        empty_pages = 0
        page_num = 1
        collected_links: list[str] = []
        seen_links: set[str] = set()

        while True:
            if self.max_pages > 0 and page_num > self.max_pages:
                logger.info("Limite de paginas atingido | max_pages=%d", self.max_pages)
                break

            listing_url = (
                f"{BASE_URL}/empresa/{quote(nome_empresa, safe='')}"
                f"/lista-reclamacoes/?pagina={page_num}"
            )

            if self._custom_fetch is None:
                links: list[str] = []
                for _ in range(self.listing_retries):
                    html = self._pw_fetch_isolated(listing_url)
                    links = self._parse_listing_links(html)
                    if links:
                        break
                    if self.delay > 0:
                        time.sleep(self.delay)
            else:
                html = self._fetch(listing_url)
                links = self._parse_listing_links(html)

            if not links:
                empty_pages += 1
                logger.warning(
                    "Pagina %d sem links | paginas_vazias=%d/%d",
                    page_num,
                    empty_pages,
                    self.max_empty_pages,
                )
                if empty_pages >= self.max_empty_pages or self._custom_fetch is not None:
                    logger.info(
                        "Encerrando listagem por paginas vazias | empresa=%s pagina=%d",
                        nome_empresa,
                        page_num,
                    )
                    break
                page_num += 1
                continue

            empty_pages = 0
            novos = 0
            for link in links:
                if link in seen_links:
                    continue
                seen_links.add(link)
                collected_links.append(link)
                novos += 1

            logger.info(
                "Pagina %d | novos_links=%d total_acumulado=%d",
                page_num,
                novos,
                len(collected_links),
            )

            if self.delay > 0:
                time.sleep(self.delay)

            page_num += 1

        logger.info(
            "Listagem concluida | empresa=%s total_links=%d paginas_percorridas=%d",
            nome_empresa,
            len(collected_links),
            page_num - 1,
        )
        return collected_links

    def _pw_fetch(self, url: str) -> str:
        if self._page is None:
            raise RuntimeError(
                "Use ReclameAquiScraper como context manager: "
                "'with ReclameAquiScraper() as s: ...'"
            )
        self._page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # Em algumas paginas o conteudo util carrega pouco depois do domcontentloaded.
        self._page.wait_for_timeout(2500)
        return self._page.content()

    def _pw_fetch_isolated(self, url: str) -> str:
        """
        Busca URL em contexto isolado para reduzir bloqueio anti-bot
        em navegacoes sequenciais (listagem e detalhe).
        """
        if self._browser is None:
            return self._pw_fetch(url)

        ctx = self._browser.new_context(
            user_agent=random.choice(_USER_AGENTS),
            locale="pt-BR",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            self._simulate_human_behavior(page)
            return page.content()
        finally:
            page.close()
            ctx.close()

    @staticmethod
    def _simulate_human_behavior(page: Page) -> None:
        # Simula interacoes leves para reduzir padrao de acesso robotico.
        page.wait_for_timeout(random.randint(800, 1800))

        viewport = page.viewport_size or {"width": 1280, "height": 900}
        width = int(viewport.get("width", 1280))
        height = int(viewport.get("height", 900))

        for _ in range(random.randint(2, 5)):
            x = random.randint(20, max(20, width - 20))
            y = random.randint(20, max(20, height - 20))
            page.mouse.move(x, y, steps=random.randint(5, 20))
            page.wait_for_timeout(random.randint(120, 350))

        scroll_steps = random.randint(3, 7)
        for _ in range(scroll_steps):
            delta = random.randint(180, 900)
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(random.randint(180, 500))

        for _ in range(random.randint(1, 3)):
            delta = -random.randint(120, 420)
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(random.randint(160, 420))

        page.wait_for_timeout(random.randint(500, 1400))

    @staticmethod
    def _parse_listing_links(html: str) -> list[str]:
        """
        Extrai links das reclamacoes da pagina de listagem.
        Estrutura: pageProps.complaints.LAST -> lista de objetos com campo url.
        """
        data = _extract_next_data(html)
        if not data:
            return []

        try:
            complaints = data["props"]["pageProps"]["complaints"]
            items: list[dict] = complaints.get("LAST", [])
        except (KeyError, TypeError):
            return []

        links: list[str] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            url_path = str(item.get("url") or "").strip()
            if url_path and not url_path.startswith("http") and not url_path.startswith("/"):
                url_path = f"/{url_path}"
            if url_path and url_path not in seen:
                seen.add(url_path)
                links.append(url_path)
        return links

    @staticmethod
    def _build_detail_url(link: str, nome_empresa: str) -> str:
        """
        Monta URL de detalhe completa.

        Alguns links da listagem chegam como '/slug_reclamacao_id' (sem empresa).
        Nesses casos, o detalhe valido fica em '/{nome_empresa}/slug_reclamacao_id/'.
        """
        raw = (link or "").strip()
        if not raw:
            return f"{BASE_URL}/{quote(nome_empresa, safe='')}/"

        if raw.startswith("http://") or raw.startswith("https://"):
            return raw

        normalized = raw if raw.startswith("/") else f"/{raw}"
        parts = [p for p in normalized.split("/") if p]
        company_slug = quote(nome_empresa, safe="")

        if len(parts) == 1:
            return f"{BASE_URL}/{company_slug}/{parts[0]}/"

        if parts[0] != company_slug:
            return f"{BASE_URL}/{company_slug}/{parts[-1]}/"

        return urljoin(f"{BASE_URL}/", "/".join(parts) + "/")

    @staticmethod
    def _parse_detail(html: str, nome_empresa: str, detail_url: str) -> Record | None:
        data = _extract_next_data(html)
        result: Record | None = None

        if data:
            def walk(node: object) -> None:
                nonlocal result
                if result:
                    return
                if isinstance(node, dict):
                    if {"title", "description"}.issubset(node.keys()):
                        local = _extract_local(node)
                        data_raw = str(node.get("createdAt") or node.get("created") or "").strip()
                        complaint_id = _extract_id(node, detail_url)
                        status = str(node.get("status") or node.get("currentStatus") or "").strip()
                        result = {
                            "titulo": str(node.get("title", "")).strip(),
                            "reclamacao": str(node.get("description", "")).strip(),
                            "local": local,
                            "data": data_raw,
                            "id": complaint_id,
                            "status": status,
                            "nome_empresa": nome_empresa,
                            "link": detail_url,
                        }
                        return
                    for v in node.values():
                        walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)

            walk(data)

        if result:
            return _merge_with_text_fallback(result, html, detail_url)

        return _parse_detail_from_text(html, nome_empresa, detail_url)


def _extract_next_data(html: str) -> object | None:
    pattern = re.compile(
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _extract_local(node: dict) -> str:
    local = str(node.get("local") or node.get("location") or "").strip()
    if local:
        return local

    city = str(node.get("city") or node.get("cidade") or "").strip()
    state = str(node.get("state") or node.get("estado") or node.get("uf") or "").strip()
    if city and state:
        return f"{city} - {state}"
    if city:
        return city
    if state:
        return state
    return ""


def _extract_id(node: dict, detail_url: str) -> str:
    for key in ("id", "complaintId", "complainId"):
        value = node.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()

    url_match = re.search(r"_([^/_?]+)/?$", detail_url)
    if url_match:
        return url_match.group(1)
    return ""

def parse_date(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%d/%m/%Y às %H:%M")

def _parse_detail_from_text(html: str, nome_empresa: str, detail_url: str) -> Record | None:
    title, complaint, date_from_ld = _extract_from_json_ld(html)
    visible_text = _extract_visible_text(html)

    date_visible = _extract_date_from_text(visible_text)
    status = _extract_status_from_text(visible_text)
    complaint_id = _extract_id_from_text(visible_text, detail_url)
    local = _extract_local_from_text(visible_text, date_visible)

    final_title = title.strip()
    final_complaint = complaint.strip()
    final_date = (date_visible or date_from_ld).strip()

    if not final_title and not final_complaint:
        return None

    return {
        "titulo": final_title,
        "reclamacao": final_complaint,
        "local": local,
        "data": parse_date(final_date).isoformat() if final_date else "",
        "id": complaint_id,
        "status": status,
        "nome_empresa": nome_empresa,
        "link": detail_url,
    }


def _merge_with_text_fallback(record: Record, html: str, detail_url: str) -> Record:
    visible_text = _extract_visible_text(html)
    record["data"] = record.get("data", "") or _extract_date_from_text(visible_text)
    record["status"] = record.get("status", "") or _extract_status_from_text(visible_text)
    record["id"] = record.get("id", "") or _extract_id_from_text(visible_text, detail_url)
    record["local"] = record.get("local", "") or _extract_local_from_text(
        visible_text,
        record.get("data", ""),
    )
    return record


def _extract_from_json_ld(html: str) -> tuple[str, str, str]:
    scripts = re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    for raw in scripts:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("@type") != "QAPage":
            continue
        main = obj.get("mainEntity")
        if not isinstance(main, dict):
            continue
        title = str(main.get("name") or "")
        text_html = str(main.get("text") or "")
        complaint = re.sub(r"<br\s*/?>", "\n", text_html, flags=re.IGNORECASE)
        complaint = re.sub(r"<[^>]+>", "", complaint)
        complaint = unescape(complaint)
        date_created = str(main.get("dateCreated") or "")
        date_visible = _extract_date_from_text(date_created)
        return title, complaint.strip(), date_visible
    return "", "", ""


def _extract_visible_text(html: str) -> str:
    cleaned = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_date_from_text(text: str) -> str:
    match = re.search(r"\b\d{2}/\d{2}/\d{4}\s+às\s+\d{2}:\d{2}\b", text)
    return match.group(0) if match else ""


def _extract_status_from_text(text: str) -> str:
    match = re.search(
        r"\b(Não respondida|Nao respondida|Respondida|Resolvida|Não resolvida|Nao resolvida|Finalizada)\b",
        text,
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def _extract_id_from_text(text: str, detail_url: str) -> str:
    match = re.search(r"\bID\s*:\s*(\d{5,})\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    fallback = re.search(r"_([^/_?]+)/?$", detail_url)
    return fallback.group(1) if fallback else ""


def _extract_local_from_text(text: str, date_text: str) -> str:
    if date_text:
        idx = text.find(date_text)
        if idx >= 0:
            window = text[max(0, idx - 220):idx]
            pattern = (
                r"([A-ZÀ-Ý][A-Za-zÀ-ÿ]+"
                r"(?:\s+(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ]+|de|da|do|dos|das)){0,5}"
                r"\s-\s[A-Z]{2})"
            )
            cands = re.findall(pattern, window)
            if cands:
                return cands[-1].strip()

    match = re.search(r"\b([A-ZÀ-Ý][A-Za-zÀ-ÿ\s]{1,40}\s-\s[A-Z]{2})\b", text)
    return match.group(1).strip() if match else ""
