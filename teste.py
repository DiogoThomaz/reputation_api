from reputation_worker.cep_api import obter_cidade, parse_cep

endereco = "R. Santos Dumont, 543 - Centro, São Miguel do Oeste - SC, 89900-000"
cep = parse_cep(endereco)
print(f"CEP extraído: {cep}")
cidade = obter_cidade(cep)
print(f"Cidade obtida: {cidade}")