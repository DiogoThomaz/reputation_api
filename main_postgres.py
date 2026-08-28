import logging
import os
import time

from reputation_worker.postgres import PostgresClient
from reputation_worker.scrapers.playstore import PlayStoreScraper
from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def _check_id_exist(db: PostgresClient, source: str, external_id: str, empresa: str) -> bool:
    result = db.execute(
        query="SELECT 1 FROM reviews_v1 WHERE source = %s AND external_id = %s AND empresa = %s",
        params=(source, external_id, empresa,),
    )
    return result["rowcount"] > 0


def _existing_ids(db: PostgresClient, source: str, empresa: str, ids: list[str]) -> set[str]:
    """Retorna os external_id ja presentes no banco (consulta em lote)."""
    if not ids:
        return set()
    placeholders = ", ".join(["%s"] * len(ids))
    result = db.execute(
        query=(
            "SELECT external_id FROM reviews_v1 "
            f"WHERE source = %s AND external_id IN ({placeholders}) AND empresa = %s"
        ),
        params=(source, *ids, empresa),
    )
    return {row["external_id"] for row in result["rows"]}


def _insert_batches(db: PostgresClient, table_cols: str, row_template: str, rows: list[dict[str, str]], chunk: int) -> None:
    """Insere em lotes multi-row: 1 round-trip por lote."""
    for start in range(0, len(rows), chunk):
        batch = rows[start : start + chunk]
        values = ", ".join([row_template] * len(batch))
        params = [value for row in batch for value in row.values()]
        db.execute(f"INSERT INTO reviews_v1 {table_cols} VALUES {values}", params)


def run_playstore(db: PostgresClient, chunk_size: int = BATCH_SIZE):
    rows = db.execute("SELECT * FROM empresa")
    empresas = rows["rows"]
    logger.info("Iniciando coleta Play Store | empresas=%d", len(empresas))

    for row in empresas:
        playstore_id = row["playstore_id"]
        empresa_nome = row["nome"]

        if not playstore_id:
            logger.warning(
                "[Play Store] Empresa sem app_id, pulando | empresa=%s",
                empresa_nome,
            )
            continue

        logger.info("[Play Store] Coletando | empresa=%s app_id=%s", empresa_nome, playstore_id)
        scrapper = PlayStoreScraper()
        reviews = list(scrapper.scrape(app_id=playstore_id))

        inseridos = 0
        pulados = 0
        for start in range(0, len(reviews), chunk_size):
            chunk = reviews[start : start + chunk_size]
            existing = _existing_ids(db, "playstore", empresa_nome, [review["id"] for review in chunk])
            novos = [review for review in chunk if review["id"] not in existing]

            pulados += len(chunk) - len(novos)
            if not novos:
                continue

            rows_to_insert = [
                {
                    "source": "playstore",
                    "empresa": empresa_nome,
                    "data": review["data"],
                    "review": review["review"],
                    "quantidade_estrelas": review["quantidade_estrelas"],
                    "external_id": review["id"],
                }
                for review in novos
            ]
            _insert_batches(
                db,
                table_cols="(source, empresa, data, review, quantidade_estrelas, external_id)",
                row_template="(%s, %s, %s, %s, %s, %s)",
                rows=rows_to_insert,
                chunk=chunk_size,
            )
            inseridos += len(novos)
            logger.debug("[Play Store] Lote inserido | empresa=%s novos=%d", empresa_nome, len(novos))

        logger.info(
            "[Play Store] Empresa concluida | empresa=%s inseridos=%d pulados=%d",
            empresa_nome, inseridos, pulados,
        )


def run_reclame_aqui(db: PostgresClient, chunk_size: int = BATCH_SIZE):
    rows = db.execute("SELECT * FROM empresa")
    empresas = rows["rows"]
    logger.info("Iniciando coleta Reclame Aqui | empresas=%d", len(empresas))

    for row in empresas:
        empresa_nome = row.get("nome", "")
        reclame_aqui_id = row.get("reclame_aqui_id")

        if not reclame_aqui_id:
            logger.warning(
                "[Reclame Aqui] Empresa sem slug, pulando | empresa=%s",
                empresa_nome,
            )
            continue

        logger.info("[Reclame Aqui] Coletando | empresa=%s slug=%s", empresa_nome, reclame_aqui_id)

        with ReclameAquiScraper(max_pages=50) as scrapper:
            reviews = list(scrapper.scrape(nome_empresa=reclame_aqui_id))

            inseridos = 0
            pulados = 0
            for start in range(0, len(reviews), chunk_size):
                chunk = reviews[start : start + chunk_size]
                existing = _existing_ids(db, "reclame_aqui", empresa_nome, [review["id"] for review in chunk])
                novos = [review for review in chunk if review["id"] not in existing]

                pulados += len(chunk) - len(novos)
                if not novos:
                    continue

                rows_to_insert = [
                    {
                        "source": "reclame_aqui",
                        "empresa": empresa_nome,
                        "data": review["data"],
                        "review": review["reclamacao"],
                        "titulo": review["titulo"],
                        "local": review["local"],
                        "external_id": review["id"],
                    }
                    for review in novos
                ]
                _insert_batches(
                    db,
                    table_cols="(source, empresa, data, review, titulo, local, external_id)",
                    row_template="(%s, %s, %s, %s, %s, %s, %s)",
                    rows=rows_to_insert,
                    chunk=chunk_size,
                )
                inseridos += len(novos)
                logger.debug("[Reclame Aqui] Lote inserido | empresa=%s novos=%d", empresa_nome, len(novos))

        logger.info(
            "[Reclame Aqui] Empresa concluida | empresa=%s inseridos=%d pulados=%d",
            empresa_nome, inseridos, pulados,
        )

def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )

    logger.info("Worker iniciado | LOG_LEVEL=%s", log_level)

    while True:
        try:
            db = PostgresClient()
            logger.info("Iniciando ciclo de coleta")
            run_reclame_aqui(db=db)
            run_playstore(db=db)
            logger.info("Ciclo de coleta finalizado")
        except Exception as e:
            logger.exception("Erro durante a coleta: %s", e)
        
        logger.info("Aguardando 3 horas")
        time.sleep(60*60*3)  # 3 horas


if __name__ == "__main__":
    main()