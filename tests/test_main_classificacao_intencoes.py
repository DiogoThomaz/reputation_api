from __future__ import annotations

import main_classificacao_intencoes as script


class FakeDB:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))
        if query.startswith("SELECT"):
            return {"rowcount": len(self.rows), "rows": self.rows}
        return {"rowcount": 1, "rows": []}


def test_get_reviews_to_classify_intents_uses_null_or_empty_filter():
    db = FakeDB(rows=[])

    script.get_reviews_to_classify_intents(db)

    assert db.calls[0][0] == "SELECT * FROM reviews_v1 WHERE intencoes IS NULL OR intencoes = ''"


def test_serialize_intents_joins_values_with_semicolon():
    assert script.serialize_intents(["reclamacao", "falta_de_retorno"]) == "reclamacao;falta_de_retorno"


def test_update_review_intents_uses_expected_query_and_params():
    db = FakeDB()

    script.update_review_intents(db, review_id=10, intencoes="reclamacao;erro_no_app")

    assert db.calls[0] == (
        "UPDATE reviews_v1 SET intencoes = %s WHERE id = %s",
        ("reclamacao;erro_no_app", 10),
    )


def test_run_classification_updates_when_intents_are_detected():
    db = FakeDB(rows=[{"id": 1, "empresa": "Acme", "review": "Atendimento demorou."}])

    stats = script.run_classification(
        db,
        classify=lambda text: {"intencoes": ["reclamacao", "demora_no_atendimento"]},
    )

    assert stats["processed"] == 1
    assert stats["updated"] == 1
    assert db.calls[-1] == (
        "UPDATE reviews_v1 SET intencoes = %s WHERE id = %s",
        ("reclamacao;demora_no_atendimento", 1),
    )


def test_run_classification_uses_reclamacao_when_review_is_empty():
    db = FakeDB(rows=[{"id": 1, "empresa": "Acme", "review": "", "reclamacao": "App com erro."}])

    stats = script.run_classification(
        db,
        classify=lambda text: {"intencoes": ["erro_no_app"]},
    )

    assert stats["updated"] == 1
    assert db.calls[-1][1] == ("erro_no_app", 1)


def test_run_classification_skips_without_text_and_does_not_update():
    db = FakeDB(rows=[{"id": 1, "empresa": "Acme", "review": "", "reclamacao": ""}])

    stats = script.run_classification(db, classify=lambda text: {"intencoes": ["reclamacao"]})

    assert stats["processed"] == 1
    assert stats["without_text"] == 1
    assert stats["updated"] == 0
    assert len(db.calls) == 1


def test_run_classification_skips_without_intents_and_does_not_update():
    db = FakeDB(rows=[{"id": 1, "empresa": "Acme", "review": "Texto valido."}])

    stats = script.run_classification(db, classify=lambda text: {"intencoes": []})

    assert stats["processed"] == 1
    assert stats["without_intents"] == 1
    assert stats["updated"] == 0
    assert len(db.calls) == 1


def test_run_classification_does_not_update_when_classifier_fails():
    db = FakeDB(rows=[{"id": 1, "empresa": "Acme", "review": "Texto valido."}])

    def classify_raises(text):
        raise RuntimeError("ollama indisponivel")

    stats = script.run_classification(db, classify=classify_raises)

    assert stats["processed"] == 1
    assert stats["errors"] == 1
    assert stats["updated"] == 0
    assert len(db.calls) == 1
