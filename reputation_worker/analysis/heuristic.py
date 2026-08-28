"""Classificacao heuristica local (sem LLM) de sentimento e intencoes.

Fallback deterministico quando Ollama/LLM nao esta disponivel.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

POSITIVOS = {
    "otimo", "excelente", "maravilhoso", "incrivel", "perfeito", "amei", "adorei",
    "gostei", "recomendo", "top", "bom", "legal", "pratico", "rapido", "facil",
    "funciona", "resolveu", "parabens", "show", "sensacional", "fantastico", "util",
    "eficiente", "satisfeito", "sucesso", "melhor", "gratuito", "leve", "estavel",
}

NEGATIVOS = {
    "pessimo", "horrivel", "terrivel", "ruim", "lixo", "odeio", "detestei", "raiva",
    "pior", "problema", "erro", "bug", "trava", "crash", "demora", "lento", "lentidao",
    "caro", "carissima", "preco", "cobranca", "cobrou", "cancelar", "cancelamento",
    "reembolso", "devolucao", "atraso", "suporte", "atendimento", "decepcao",
    "decepcionado", "frustrado", "falta", "golpe", "fraude", "virus", "propaganda",
    "notificacao", "atualizacao", "quebrou", "estragou", "defeito", "mentira",
    "engana", "falso", "paguei", "dinheiro", "impossivel", "inutilizavel", "lixo",
}

# intencao -> palavras-chave (em ordem de prioridade)
INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "elogio": ("otimo", "excelente", "amei", "adorei", "recomendo", "parabens", "maravilhoso", "top", "muito bom", "gostei"),
    "problema_tecnico": ("trava", "bug", "crash", "app fecha", "nao abre", "nao funciona", "lento", "congela"),
    "erro_no_app": ("erro", "falha", "tela preta", "nao carrega", "fecha sozinho", "reinicia"),
    "demora_no_atendimento": ("demora", "horas", "dias esperando", "espera", "sem resposta", "nao respondem"),
    "atendimento_ruim": ("atendimento", "suporte", "grosseiro", "sem educacao", "ignoraram"),
    "cobranca_indevida": ("cobranca", "cobrou", "cobraram", "cobrando", "debito", "taxa", "tarifa", "juros"),
    "reembolso": ("reembolso", "estorno", "devolucao", "devolver", "dinheiro de volta"),
    "cancelamento": ("cancelar", "cancelamento", "assinatura", "renovacao"),
    "problema_com_pagamento": ("pagamento", "compra", "pix", "cartao", "boleto", "negado"),
    "prazo_nao_cumprido": ("atraso", "prazo", "nao chegou", "entrega"),
    "preco_alto": ("caro", "carissima", "preco alto", "aumentou", "mensalidade", "carissimo"),
    "qualidade_baixa": ("qualidade", "fragil", "terrivel", "horrivel", "pessimo"),
    "suporte_ineficiente": ("suporte", "nao resolvem", "chat", "email", "ninguem responde"),
    "servico_indisponivel": ("indisponivel", "fora do ar", "offline", "sem servico"),
    "dificuldade_de_acesso": ("nao consigo entrar", "login", "senha", "acesso", "conta", "logar"),
    "falta_de_retorno": ("sem retorno", "nao respondem", "ignoraram", "sumiram"),
    "informacao_incorreta": ("informacao errada", "mentira", "engana", "falso", "enganado"),
    "duvida": ("como", "quando", "onde", "posso", "duvida", "ajuda", "preciso"),
    "sugestao": ("sugestao", "seria bom", "melhorar", "poderia", "adicionar", "espero que", "gostaria"),
    "experiencia_positiva": ("funciona", "rapido", "pratico", "facil", "gratuito", "uso todo dia"),
}

MAX_INTENTS = 3


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _normalize(text)))


def _lexical_score(text: str) -> int:
    tokens = _tokenize(text)
    positives = tokens & POSITIVOS
    negatives = tokens & NEGATIVOS
    score = len(positives) - len(negatives)
    lowered = _normalize(text)
    # correcao de negacao composta: "nao funciona" nao e positivo
    for phrase in ("nao funciona", "nao carrega", "nao abre", "nao consigo"):
        if phrase in lowered:
            score -= 2
    return score


def classify_sentiment(review: str, estrelas: str | int | None = None) -> str:
    review = (review or "").strip()
    if not review:
        return "neutro"

    score = _lexical_score(review)

    if estrelas is not None:
        try:
            stars = int(estrelas)
        except (TypeError, ValueError):
            stars = 0
        if stars >= 4:
            score += 1
        elif stars <= 2:
            score -= 1

    if score > 0:
        return "positivo"
    if score < 0:
        return "negativo"
    return "neutro"


def classify_intents(review: str) -> list[str]:
    review = (review or "").strip()
    if not review:
        return []

    lowered = _normalize(review)
    matched: list[tuple[int, str]] = []
    for intent, keywords in INTENT_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in lowered)
        if hits:
            matched.append((hits, intent))

    # negacao composta: "nao funciona" nao deve gerar intencao positiva
    if any(phrase in lowered for phrase in ("nao funciona", "nao carrega", "nao abre")):
        matched = [(hits, intent) for hits, intent in matched if intent not in ("elogio", "experiencia_positiva")]

    matched.sort(key=lambda item: (-item[0], item[1]))
    return [intent for _, intent in matched[:MAX_INTENTS]]


def analyze(review: str, estrelas: str | int | None = None) -> dict[str, Any]:
    return {
        "sentimento": classify_sentiment(review, estrelas),
        "intencoes": classify_intents(review),
    }