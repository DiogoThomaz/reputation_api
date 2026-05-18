import logging
import os
import time

from reputation_worker.postgres import PostgresClient
from reputation_worker.scrapers.playstore import PlayStoreScraper
from reputation_worker.scrapers.reclame_aqui import ReclameAquiScraper

logger = logging.getLogger(__name__)

def _check_id_exist(db: PostgresClient, source: str, external_id: str, empresa: str) -> bool:
        
        result = db.execute(
            query="SELECT 1 FROM reviews_v1 WHERE source = %s AND external_id = %s AND empresa = %s",
            params=(source, external_id, empresa,),
        )
        return result["rowcount"] > 0

def run_playstore(db: PostgresClient, call_check_id: callable = _check_id_exist):
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
        reviews = scrapper.scrape(app_id=playstore_id)

        inseridos = 0
        pulados = 0
        for review in reviews:
            exist = call_check_id(db, "playstore", review["id"], empresa_nome)
            if exist:
                logger.debug("[Play Store] Review ja existe, pulando | id=%s empresa=%s", review["id"], empresa_nome)
                pulados += 1
                continue

            db.execute(
                query="insert into reviews_v1 (source, empresa, data, review, quantidade_estrelas, external_id) values (%s, %s, %s, %s, %s, %s)",
                params=("playstore", empresa_nome, review["data"], review["review"], review["quantidade_estrelas"], review["id"],),
            )
            inseridos += 1
            logger.debug("[Play Store] Review inserido | id=%s empresa=%s", review["id"], empresa_nome)

        logger.info(
            "[Play Store] Empresa concluida | empresa=%s inseridos=%d pulados=%d",
            empresa_nome, inseridos, pulados,
        )


def run_reclame_aqui(db: PostgresClient, call_check_id: callable = _check_id_exist):
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
            reviews = scrapper.scrape(nome_empresa=reclame_aqui_id)

            inseridos = 0
            pulados = 0
            for review in reviews:
                exist = call_check_id(db, "reclame_aqui", review["id"], empresa_nome)
                if exist:
                    logger.debug("[Reclame Aqui] Review ja existe, pulando | id=%s empresa=%s", review["id"], empresa_nome)
                    pulados += 1
                    continue

                db.execute(
                    query="insert into reviews_v1 (source, empresa, data, review, titulo, local, external_id) values (%s, %s, %s, %s, %s, %s, %s)",
                    params=("reclame_aqui", empresa_nome, review["data"], review["reclamacao"], review["titulo"], review["local"], review["id"],),
                )
                inseridos += 1
                logger.debug("[Reclame Aqui] Reclamacao inserida | id=%s empresa=%s titulo=%s", review["id"], empresa_nome, review.get("titulo", "")[:60])

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
            run_reclame_aqui(db=db, call_check_id=_check_id_exist)
            run_playstore(db=db, call_check_id=_check_id_exist)
            logger.info("Ciclo de coleta finalizado")
        except Exception as e:
            logger.exception("Erro durante a coleta: %s", e)
        
        logger.info("Aguardando 3 horas")
        time.sleep(60*60*3)  # 3 horas


if __name__ == "__main__":
    main()