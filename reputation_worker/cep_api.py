from requests import requests


def parse_cep(endereco: str) -> str:
    cep = endereco.split(", ")[-1].strip()
    if cep.isdigit() and len(cep) == 8:
        return cep
    return ""

def obter_cidade(cep: str) -> str:
    url = f"https://viacep.com.br/ws/{cep}/json/"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get("localidade", "Cidade não encontrada")
    else:
        return "Erro ao obter cidade"