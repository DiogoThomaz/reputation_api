from __future__ import annotations

from dataclasses import dataclass

from reputation_worker.agent.intent_agent import classify_review_intent


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


def test_classify_review_intent_single_valid_intent():
    result = classify_review_intent(
        "O atendimento foi excelente.",
        agent=FakeAgent('{"intencoes": ["elogio"]}'),
    )

    assert result == {"intencoes": ["elogio"]}


def test_classify_review_intent_multiple_valid_intents():
    result = classify_review_intent(
        "O atendimento demorou muito e ninguem retornou.",
        agent=FakeAgent('{"intencoes": ["reclamacao", "demora_no_atendimento", "falta_de_retorno"]}'),
    )

    assert result == {"intencoes": ["reclamacao", "demora_no_atendimento", "falta_de_retorno"]}


def test_classify_review_intent_extracts_json_from_extra_text():
    result = classify_review_intent(
        "O app sempre da erro ao pagar.",
        agent=FakeAgent('Resultado: {"intencoes": ["erro_no_app", "problema_com_pagamento"]} fim.'),
    )

    assert result == {"intencoes": ["erro_no_app", "problema_com_pagamento"]}


def test_classify_review_intent_normalizes_accents_spaces_and_hyphens():
    result = classify_review_intent(
        "Recebi uma cobrança incorreta.",
        agent=FakeAgent('{"intencoes": ["Cobrança Indevida", "suporte-ineficiente"]}'),
    )

    assert result == {"intencoes": ["cobranca_indevida", "suporte_ineficiente"]}


def test_classify_review_intent_removes_invalid_and_duplicate_intents():
    result = classify_review_intent(
        "Quero cancelar e pedir reembolso.",
        agent=FakeAgent('{"intencoes": ["cancelamento", "cancelamento", "furia", "reembolso"]}'),
    )

    assert result == {"intencoes": ["cancelamento", "reembolso"]}


def test_classify_review_intent_accepts_string_intent():
    result = classify_review_intent(
        "Tenho uma duvida sobre o prazo.",
        agent=FakeAgent('{"intencoes": "duvida"}'),
    )

    assert result == {"intencoes": ["duvida"]}


def test_classify_review_intent_limits_to_three_items():
    result = classify_review_intent(
        "Muitos problemas no pedido.",
        agent=FakeAgent(
            '{"intencoes": ['
            '"reclamacao", "atendimento_ruim", "demora_no_atendimento", '
            '"falta_de_retorno", "suporte_ineficiente"'
            "]}"
        ),
    )

    assert result == {"intencoes": ["reclamacao", "atendimento_ruim", "demora_no_atendimento"]}


def test_classify_review_intent_empty_review_returns_empty_without_agent_call():
    agent = FakeAgent('{"intencoes": ["elogio"]}')

    result = classify_review_intent("   ", agent=agent)

    assert result == {"intencoes": []}
    assert agent.inputs == []
