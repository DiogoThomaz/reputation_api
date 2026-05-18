# reputation_api - worker de reputacao

## O que foi implementado

- Modulo de hook HTTP com POST JSON.
- Modulo de scrapper com:
  - `chunk_yield` (envio em lotes)
  - `source` (factory: `playstore` e `reclame_aqui`)
  - `callback` externo para envio dos dados
- Scraper Reclame Aqui: retorna `titulo`, `reclamacao`, `data`, `nome_empresa`.
- Scraper Play Store: retorna `review`, `data`, `quantidade_estrelas`.
- Testes unitarios cobrindo hook, factory, worker e parsers.
- Integracao com RabbitMQ para consumir jobs e enviar resultado para `hook_url`.

## Estrutura

- `reputation_worker/hook.py`
- `reputation_worker/worker.py`
- `reputation_worker/scrapers/factory.py`
- `reputation_worker/scrapers/reclame_aqui.py`
- `reputation_worker/scrapers/playstore.py`
- `tests/`

## RabbitMQ

Foi adicionado um consumer que le jobs da fila e executa o fluxo:

1. Recebe job JSON da fila
2. Valida campos (`source`, `name`, `hook_url`)
3. Executa scraping com `ScraperWorker`
4. Envia lotes para o hook HTTP informado no proprio job

### Formato do job (entrada — mensagem publicada na fila)

```json
{
  "source": "playstore",
  "name": "nubank",
  "hook_url": "https://seu-endpoint.com/hook"
}
```

| Campo      | Tipo   | Obrigatório             | Descrição                                      |
|------------|--------|-------------------------|------------------------------------------------|
| `source`   | string | Sim                     | `playstore` ou `reclame_aqui`                  |
| `name`     | string | Sim                     | Slug da empresa (Reclame Aqui) ou ID do app (Play Store) |
| `hook_url` | string | Somente se `WORKER_USE_LOCAL_HOOK=false` | Endpoint HTTP(S) que receberá os lotes de registros |

### Output do job — payload enviado ao hook

Os registros são enviados em lotes ao `hook_url` (ou gravados no xlsx em modo local) à medida que são coletados, conforme configurado em `WORKER_CHUNK_YIELD`.

**Envelope do lote:**

```json
{
  "records": [ ... ]
}
```

**Campos por registro — `reclame_aqui`:**

```json
{
  "titulo":       "Não recebi meu certificado",
  "reclamacao":   "Texto completo da reclamação...",
  "local":        "São Paulo, SP",
  "data":         "2024-03-15T10:22:00.000Z",
  "id":           "XXXXXXXXXXX",
  "status":       "Resolvido",
  "nome_empresa": "cna-ingles-e-espanhol",
  "link":         "https://www.reclameaqui.com.br/cna-ingles-e-espanhol/titulo-da-reclamacao_id/"
}
```

| Campo         | Descrição                                          |
|---------------|----------------------------------------------------|
| `titulo`      | Título da reclamação                               |
| `reclamacao`  | Corpo completo da reclamação                       |
| `local`       | Cidade e estado do reclamante                      |
| `data`        | Data de criação (ISO 8601 ou string original)      |
| `id`          | Identificador único da reclamação no Reclame Aqui  |
| `status`      | Status atual (ex.: `Resolvido`, `Não respondida`)  |
| `nome_empresa`| Slug da empresa consultada                         |
| `link`        | URL completa da reclamação                         |

**Campos por registro — `playstore`:**

```json
{
  "review":              "Ótimo app, recomendo!",
  "data":                "2024-03-15 10:22:00",
  "quantidade_estrelas": "5"
}
```

| Campo                | Descrição                          |
|----------------------|------------------------------------|
| `review`             | Texto da avaliação                 |
| `data`               | Data da avaliação                  |
| `quantidade_estrelas`| Nota de 1 a 5                      |

### Variaveis no .env

- `RABBITMQ_HOST`
- `RABBITMQ_PORT`
- `RABBITMQ_VHOST`
- `RABBITMQ_USERNAME`
- `RABBITMQ_PASSWORD`
- `RABBITMQ_QUEUE`
- `RABBITMQ_URL` (opcional, pode ser usado em vez de host/porta/vhost)
- `RABBITMQ_USE_TLS`
- `RABBITMQ_PREFETCH_COUNT`
- `WORKER_CHUNK_YIELD`

### Rodar consumer

```bash
python main_rabbitmq.py
```

## Postgres

Foi adicionado um cliente simples para executar queries parametrizadas no PostgreSQL.

### Variaveis no .env

- `POSTGRES_HOST`
- `POSTGRES_DATABASE`
- `POSTGRES_USERNAME`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT` (opcional, padrao `5432`)
- `POSTGRES_SSLMODE` (opcional)
- `POSTGRES_CONNECT_TIMEOUT` (opcional, padrao `10`)

### Exemplo de uso

```python
from reputation_worker import PostgresClient

client = PostgresClient()

resultado = client.execute(
  "SELECT id, nome FROM empresas WHERE id = %s",
  (1,),
)

print(resultado)
```

Retorno esperado:

```python
{
  "rowcount": 1,
  "rows": [{"id": 1, "nome": "Acme"}],
}
```

## Executar testes

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Futuro

- Integrar `ScraperWorker` com dispatcher RabbitMQ no modulo `QueueDispatcher`.
