from reputation_worker.scrapers.google_maps import GoogleMapsScraper
from reputation_worker.postgres import PostgresClient
import logging
import asyncio

def selecionar_lista_unica_empresas(db: PostgresClient) -> list[str]:
    result = db.execute("SELECT DISTINCT nome FROM empresa")
    return [row["nome"] for row in result["rows"]]

def selecionar_cidades_unicas(db: PostgresClient) -> list[str]:
    result = db.execute("SELECT DISTINCT local FROM reviews_v1")
    return [row["local"] for row in result["rows"]]

def salvar_cadastro_empresa(db: PostgresClient, data: dict) -> None:
    response = db.execute(
        query="INSERT INTO localizacao_empresas (nome, telefone, endereço, cidade, email, site, rede) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        params=(
            data.get("nome"),
            data.get("telefone"),
            data.get("endereco"),
            data.get("cidade"),
            data.get("email"),
            data.get("site"),
            data.get("setor"),
        ),
    )
    print(response)

def checar_empresa_existe(db: PostgresClient, nome: str, cidade: str, endereco: str) -> bool:
    result = db.execute(
        query="SELECT 1 FROM localizacao_empresas WHERE nome = %s AND cidade = %s AND endereço = %s",
        params=(nome, cidade, endereco,),
    )
    return result["rowcount"] > 0

async def main():
    db = PostgresClient()
    scrapper = GoogleMapsScraper(
        empresas=selecionar_lista_unica_empresas(db),
        cidades=selecionar_cidades_unicas(db),
    )

    async for r in scrapper.coletar():
        try:
            print(r)
            if checar_empresa_existe(db, r["nome"], r["cidade"], r["endereco"]):
                logging.info(f"Empresa já existe no banco, pulando cadastro: {r['nome']} - {r['cidade']} - {r['endereco']}")
                continue
            salvar_cadastro_empresa(db, r)
        except Exception as exc:
            logging.error(f"Erro ao salvar dados no banco: {exc}")

if __name__ == "__main__":
    asyncio.run(main())
    print("Coleta finalizada")