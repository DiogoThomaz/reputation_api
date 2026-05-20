from __future__ import annotations

from dataclasses import dataclass

from reputation_worker.agent.sentiment_agent import classify_review_sentiment


@dataclass
class FakeResponse:
    content: str


class FakeAgent:
    def __init__(self, content: str):
        self.content = content
        self.inputs: list[str] = []

    def run(self, input: str):
        self.inputs.append(input)
        return FakeResponse(self.content)


def test_classify_review_sentiment_positive_json():
    result = classify_review_sentiment(
        "Atendimento excelente e resolveram meu problema rapidamente.",
        agent=FakeAgent('{"sentimento": "positivo"}'),
    )

    assert result == {"sentimento": "positivo"}


def test_classify_review_sentiment_negative_json():
    result = classify_review_sentiment(
        "Pessimo atendimento, ninguem resolveu nada.",
        agent=FakeAgent('{"sentimento": "negativo"}'),
    )

    assert result == {"sentimento": "negativo"}


def test_classify_review_sentiment_neutral_json():
    result = classify_review_sentiment(
        "Usei o produto ontem.",
        agent=FakeAgent('{"sentimento": "neutro"}'),
    )

    assert result == {"sentimento": "neutro"}


def test_classify_review_sentiment_extracts_json_from_extra_text():
    result = classify_review_sentiment(
        "Demorou muito e nao gostei.",
        agent=FakeAgent('Claro. {"sentimento": "negativo"} Obrigado.'),
    )

    assert result == {"sentimento": "negativo"}


def test_classify_review_sentiment_invalid_sentiment_falls_back_to_neutral():
    result = classify_review_sentiment(
        "Texto qualquer.",
        agent=FakeAgent('{"sentimento": "misto"}'),
    )

    assert result == {"sentimento": "neutro"}


def test_classify_review_sentiment_empty_review_returns_neutral_without_agent_call():
    agent = FakeAgent('{"sentimento": "positivo"}')

    result = classify_review_sentiment("   ", agent=agent)

    assert result == {"sentimento": "neutro"}
    assert agent.inputs == []
