import logging
import os

from reputation_worker.agent import classify_review_sentiment
from reputation_worker.postgres import PostgresClient


logger = logging.getLogger(__name__)



def get_reviews_to_classify(db: PostgresClient):
    result = db.execute(
        query="SELECT * FROM reviews_v1 WHERE sentimento IS NULL",
    )

    return result["rows"]


def update_review_sentiment(db: PostgresClient, review_id: int, sentimento: str) -> None:
    db.execute(
        query="UPDATE reviews_v1 SET sentimento = %s WHERE id = %s",
        params=(sentimento, review_id),
    )


def main() -> None:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        force=True,
    )

    db = PostgresClient()
    reviews = get_reviews_to_classify(db)
    logger.info("Iniciando classificacao de sentimentos | total=%d", len(reviews))

    processed = 0
    updated = 0
    errors = 0

    for review in reviews:
        review_id = review["id"]
        empresa = review.get("empresa", "")
        text = review.get("review") or review.get("reclamacao") or ""
        processed += 1

        try:
            logger.info("Classificando review | id=%s empresa=%s", review_id, empresa)
            result = classify_review_sentiment(text)
            review = text
            logger.info(f"Review {review} ")
            sentimento = result["sentimento"]
            logger.info(sentimento)
            update_review_sentiment(db, review_id=review_id, sentimento=sentimento)
            updated += 1
            logger.info("Review classificado | id=%s sentimento=%s", review_id, sentimento)
        except Exception:
            errors += 1
            logger.exception("Erro ao classificar review | id=%s empresa=%s", review_id, empresa)

    logger.info(
        "Classificacao finalizada | processados=%d atualizados=%d erros=%d",
        processed,
        updated,
        errors,
    )


if __name__ == "__main__":
    main()
