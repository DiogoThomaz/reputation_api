"""Analisador de reviews: LLM (Ollama/agno) quando disponivel, heuristico como fallback."""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from reputation_worker.agent.common import DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL
from reputation_worker.agent.intent_agent import classify_review_intent
from reputation_worker.agent.sentiment_agent import classify_review_sentiment
from reputation_worker.analysis.heuristic import analyze as analyze_heuristic

logger = logging.getLogger(__name__)


def ollama_ready(host: str | None = None, model: str | None = None, timeout: float = 2.0) -> bool:
    """True apenas se o Ollama responde E o modelo configurado esta presente."""
    host_url = host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
    model_id = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    try:
        response = httpx.get(host_url.rstrip("/") + "/api/tags", timeout=timeout)
        if response.status_code != 200:
            return False
        models = {item.get("name", "").split(":")[0] for item in response.json().get("models", [])}
        return model_id.split(":")[0] in models
    except Exception:
        return False


class ReviewAnalyzer:
    """Classifica sentimento + intencoes de um review.

    Com Ollama disponivel usa os agentes existentes (agno); sem Ollama (ou
    em falha pontual) cai para a classificacao heuristica local.
    """

    def __init__(self, use_llm: bool | None = None) -> None:
        if use_llm is None:
            use_llm = ollama_ready()
        self.use_llm = use_llm
        self._sentiment_agent = None
        self._intent_agent = None

    @property
    def sentiment_agent(self):
        if self._sentiment_agent is None:
            from reputation_worker.agent.sentiment_agent import build_sentiment_agent

            self._sentiment_agent = build_sentiment_agent()
        return self._sentiment_agent

    @property
    def intent_agent(self):
        if self._intent_agent is None:
            from reputation_worker.agent.intent_agent import build_intent_agent

            self._intent_agent = build_intent_agent()
        return self._intent_agent

    def analyze(self, review: str, estrelas: str | int | None = None) -> dict[str, Any]:
        if self.use_llm:
            try:
                sentimento = classify_review_sentiment(review, self.sentiment_agent)["sentimento"]
                intencoes = classify_review_intent(review, self.intent_agent)["intencoes"]
                return {"sentimento": sentimento, "intencoes": intencoes}
            except Exception:
                logger.exception("LLM falhou, usando classificacao heuristica")
        return analyze_heuristic(review, estrelas)