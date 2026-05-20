import logging
import os
from collections.abc import Callable
from typing import Any

from reputation_worker.agent import classify_review_intent
from reputation_worker.postgres import PostgresClient


logger = logging.getLogger(__name__)


def get_reviews_to_classify_intents(db: PostgresClient) -> list[dict[str, Any]]:
    result = db.execute(
        query="SELECT * FROM reviews_v1 WHERE intencoes IS NULL OR intencoes = ''",
    )
    return result["rows"]


def update_review_intents(db: PostgresClient, review_id: int, intencoes: str) -> None:
    db.execute(
        query="UPDATE reviews_v1 SET intencoes = %s WHERE id = %s",
        params=(intencoes, review_id),
    )


def serialize_intents(intencoes: list[str]) -> str:
    return ";".join(intencoes)


def get_review_text(review: dict[str, Any]) -> str:
    return (review.get("review") or review.get("reclamacao") or "").strip()


def run_classification(
    db: PostgresClient,
    classify: Callable[[str], dict[str, list[str]]] = classify_review_intent,
) -> dict[str, int]:
    reviews = get_reviews_to_classify_intents(db)
    logger.info("Iniciando classificacao de intencoes | total=%d", len(reviews))

    stats = {
        "processed": 0,
        "updated": 0,
        "without_text": 0,
        "without_intents": 0,
        "errors": 0,
    }

    for review in reviews:
        review_id = review["id"]
        empresa = review.get("empresa", "")
        stats["processed"] += 1

        try:
            text = get_review_text(review)
            if not text:
                stats["without_text"] += 1
                logger.warning("Review sem texto, nao sera atualizado | id=%s empresa=%s", review_id, empresa)
                continue

            logger.info("Classificando intencoes | id=%s empresa=%s", review_id, empresa)
            result = classify(text)
            intencoes = result.get("intencoes") or []
            if not intencoes:
                stats["without_intents"] += 1
                logger.warning("Nenhuma intencao detectada, nao sera atualizado | id=%s empresa=%s", review_id, empresa)
                continue

            intencoes_db = serialize_intents(intencoes)
            logger.info("Review:\n%s\nIntencoes:\n%s", text, intencoes_db)
            update_review_intents(db, review_id=review_id, intencoes=intencoes_db)
            stats["updated"] += 1
            logger.info("Review atualizado | id=%s intencoes=%s", review_id, intencoes_db)
        except Exception:
            stats["errors"] += 1
            logger.exception("Erro ao classificar intencoes, nada foi salvo | id=%s empresa=%s", review_id, empresa)

    logger.info(
        "Classificacao de intencoes finalizada | processados=%d atualizados=%d sem_texto=%d sem_intencoes=%d erros=%d",
        stats["processed"],
        stats["updated"],
        stats["without_text"],
        stats["without_intents"],
        stats["errors"],
    )
    return stats


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )

    db = PostgresClient()
    run_classification(db)


if __name__ == "__main__":
    main()
