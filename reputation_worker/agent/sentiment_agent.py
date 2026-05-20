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
)


ALLOWED_SENTIMENTS = {"positivo", "negativo", "neutro"}


def _normalize_sentiment(value: Any) -> str:
    sentiment = str(value or "").strip().lower()
    if sentiment not in ALLOWED_SENTIMENTS:
        return "neutro"
    return sentiment


def build_sentiment_agent(model: str | None = None, host: str | None = None) -> Agent:
    model_id = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    host_url = host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)

    return Agent(
        name="sentiment-review-classifier",
        model=Ollama(id=model_id, host=host_url, options={"temperature": 0.1}),
        instructions=[
            "Voce e um classificador de sentimento de reviews de clientes.",
            "Classifique o sentimento geral do cliente como exatamente: positivo, negativo ou neutro.",
            "Retorne apenas JSON valido, sem markdown, sem explicacoes e sem texto adicional.",
            'O formato obrigatorio e: {"sentimento": "positivo"}',
        ],
        markdown=False,
    )


def classify_review_sentiment(review: str, agent: Agent | None = None) -> dict[str, str]:
    review = (review or "").strip()
    if not review:
        return {"sentimento": "neutro"}

    sentiment_agent = agent or build_sentiment_agent()
    response = sentiment_agent.run(
        "Classifique o sentimento do review abaixo e responda somente no JSON solicitado.\n\n"
        f"Review:\n{review}"
    )
    content = response_content(response)
    parsed = extract_json_object(content)
    return {"sentimento": _normalize_sentiment(parsed.get("sentimento"))}
