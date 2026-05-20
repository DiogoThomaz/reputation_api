from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from reputation_worker.cep_api import obter_cidade, parse_cep
from reputation_worker.postgres import PostgresClient


CHUNK_SIZE = 500
INVALID_CITY_RESPONSES = {"", "Cidade não encontrada", "Erro ao obter cidade"}

logger = logging.getLogger(__name__)


def fetch_location_chunk(db: PostgresClient, limit: int, offset: int) -> list[dict[str, Any]]:
    result = db.execute(
        query=(
            'SELECT id, "endereço", cidade '
            "FROM localizacao_empresas "
            "ORDER BY id "
            "LIMIT %s OFFSET %s"
        ),
        params=(limit, offset),
    )
    return result["rows"]

def fetch_all_locations(db: PostgresClient) -> list[dict[str, Any]]:
    result = db.execute(query='SELECT COUNT(*) AS count FROM localizacao_empresas')
    total = result["rows"][0]["count"]
    logger.info("Total de registros a processar: %d", total)

    all_locations = []
    for offset in range(0, total, CHUNK_SIZE):
        chunk = fetch_location_chunk(db, CHUNK_SIZE, offset)
        all_locations.extend(chunk)
        logger.info("Processados %d/%d registros", min(offset + CHUNK_SIZE, total), total)

    return all_locations


def update_city(db: PostgresClient, row_id: int, city: str) -> None:
    db.execute(
        query="UPDATE localizacao_empresas SET cidade = %s WHERE id = %s",
        params=(city, row_id),
    )


def main():
    db = PostgresClient()
    locations = fetch_all_locations(db)
    logger.info("Iniciando atualização de cidades")
    for location in locations:
        try:
            cidade = location["cidade"]
            endereco = location["endereço"]

            print(f"Processando ID {location['id']} | Endereço: {endereco} | Cidade atual: {cidade}")

            cep = parse_cep(endereco)
            print(f"CEP extraído: {cep}")
            cidade_consulta = obter_cidade(cep)
            print(f"Cidade obtida: {cidade_consulta}")

            if cidade_consulta != cidade:
                db.execute(
                    query="UPDATE localizacao_empresas SET cidade = %s WHERE id = %s",
                    params=(cidade_consulta, location["id"]),
                )
                logger.info("******** Atualizada cidade | id=%d cidade_antiga=%s cidade_nova=%s", location["id"], cidade, cidade_consulta)
        except Exception as e:
            logger.error("Erro ao processar ID %d: %s", location["id"], str(e))

    logger.info("Atualização de cidades finalizada")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
