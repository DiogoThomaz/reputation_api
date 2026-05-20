from __future__ import annotations

import os
from typing import Any

from agno.agent import Agent
from agno.models.ollama import Ollama

from reputation_worker.agent.common import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    extract_json_object,
    response_content,
    to_snake_case,
)


ALLOWED_INTENTS = {
    "elogio",
    "reclamacao",
    "sugestao",
    "duvida",
    "atendimento_ruim",
    "demora_no_atendimento",
    "problema_tecnico",
    "cobranca_indevida",
    "cancelamento",
    "reembolso",
    "entrega_atrasada",
    "produto_defeituoso",
    "servico_indisponivel",
    "dificuldade_de_acesso",
    "erro_no_app",
    "falta_de_retorno",
    "informacao_incorreta",
    "preco_alto",
    "qualidade_baixa",
    "problema_com_pagamento",
    "prazo_nao_cumprido",
    "suporte_ineficiente",
    "experiencia_positiva",
    "melhoria_de_produto",
}


def _normalize_intents(value: Any, max_items: int = 3) -> list[str]:
    if isinstance(value, str):
        raw_intents = [value]
    elif isinstance(value, list):
        raw_intents = value
    else:
        raw_intents = []

    intents: list[str] = []
    seen: set[str] = set()
    for raw_intent in raw_intents:
        intent = to_snake_case(raw_intent)
        if intent not in ALLOWED_INTENTS or intent in seen:
            continue
        seen.add(intent)
        intents.append(intent)
        if len(intents) >= max_items:
            break
    return intents


def build_intent_agent(model: str | None = None, host: str | None = None) -> Agent:
    model_id = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    host_url = host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    allowed_intents = ", ".join(sorted(ALLOWED_INTENTS))

    return Agent(
        name="intent-review-classifier",
        model=Ollama(id=model_id, host=host_url, options={"temperature": 0.1}),
        instructions=[
            "Voce e um classificador de intencoes de clientes em reviews.",
            "Classifique o review usando apenas as intencoes permitidas.",
            "Retorne uma lista curta com 1 a 3 intencoes mais relevantes.",
            "Retorne apenas JSON valido, sem markdown, sem explicacoes e sem texto adicional.",
            'O formato obrigatorio e: {"intencoes": ["reclamacao"]}',
            f"Intencoes permitidas: {allowed_intents}.",
        ],
        markdown=False,
    )


def classify_review_intent(review: str, agent: Agent | None = None) -> dict[str, list[str]]:
    review = (review or "").strip()
    if not review:
        return {"intencoes": []}

    intent_agent = agent or build_intent_agent()
    response = intent_agent.run(
        "Classifique as intencoes do cliente no review abaixo e responda somente no JSON solicitado.\n\n"
        f"Review:\n{review}"
    )
    content = response_content(response)
    parsed = extract_json_object(content)
    return {"intencoes": _normalize_intents(parsed.get("intencoes"))}
