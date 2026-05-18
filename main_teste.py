"""Script de teste para coletar dados e salvar localmente em planilha."""

from __future__ import annotations

import logging

from reputation_worker.hook_local import HookClientLocal
from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper
from reputation_worker.worker import ScraperWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------
# Configuracoes - ajuste conforme o alvo desejado
# ----------------------------------------------------------
SOURCE = "reclame_aqui"              # ou "playstore"
SOURCE_INPUT = "cna-ingles-e-espanhol"  # slug da empresa ou id do app
CHUNK_YIELD = 5                      # salva na planilha a cada N registros
MAX_PAGES = 50                        # maximo de paginas de listagem
DELAY_SECONDS = 3.0                  # atraso entre requests para reduzir bloqueio
LISTING_RETRIES = 4                  # tentativas por pagina de listagem
DETAIL_RETRIES = 4                   # tentativas por pagina de detalhe
MAX_EMPTY_PAGES = 5                  # tolera paginas vazias antes de encerrar
OUTPUT_FILE = "resultado.xlsx"
SHEET_NAME = "reclamacoes"
HEADLESS = True                      # False para ver o browser abrindo
# ----------------------------------------------------------


def build_callback(hook: HookClientLocal):
    def callback(records: list[dict]) -> None:
        result = hook.post({"records": records})
        logger.info(
            "Lote salvo | registros=%d linhas_escritas=%d arquivo=%s",
            len(records),
            result["rows_written"],
            OUTPUT_FILE,
        )
    return callback


def main() -> None:
    hook = HookClientLocal(file_path=OUTPUT_FILE, sheet_name=SHEET_NAME)
    callback = build_callback(hook)

    if SOURCE == "reclame_aqui":
        scraper = ReclameAquiScraper(
            max_pages=MAX_PAGES,
            delay=DELAY_SECONDS,
            listing_retries=LISTING_RETRIES,
            detail_retries=DETAIL_RETRIES,
            max_empty_pages=MAX_EMPTY_PAGES,
            headless=HEADLESS,
        )
        with scraper:
            worker = ScraperWorker(
                source=SOURCE,
                chunk_yield=CHUNK_YIELD,
                callback=callback,
                scraper=scraper,
            )
            logger.info("Coletando dados | source=%s input=%s", SOURCE, SOURCE_INPUT)
            total = worker.run(SOURCE_INPUT)
    else:
        worker = ScraperWorker(
            source=SOURCE,
            chunk_yield=CHUNK_YIELD,
            callback=callback,
        )
        logger.info("Coletando dados | source=%s input=%s", SOURCE, SOURCE_INPUT)
        total = worker.run(SOURCE_INPUT)

    logger.info("Coleta concluida | total_registros=%d planilha=%s", total, OUTPUT_FILE)


if __name__ == "__main__":
    main()
