import json
import requests


def parse_cep(endereco: str) -> str:
    cep = endereco.split(",")[-1]
    return cep

def obter_cidade(cep: str) -> str:
    cep_temp = cep.replace("-", "").strip()
    url = f"https://viacep.com.br/ws/{cep_temp}/json/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    data = json.loads(response.text)
    endereco = f'{data["localidade"]} - {data["uf"]}'
    return endereco