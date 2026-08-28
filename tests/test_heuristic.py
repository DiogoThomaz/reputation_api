import unittest

from reputation_worker.analysis.heuristic import (
    classify_intents,
    classify_sentiment,
)


class TestClassifySentiment(unittest.TestCase):
    def test_positivo_por_lexico(self):
        self.assertEqual(classify_sentiment("Ótimo app, excelente, recomendo!"), "positivo")

    def test_negativo_por_lexico(self):
        self.assertEqual(classify_sentiment("Péssimo app, odeio, lixo total"), "negativo")

    def test_negacao_composta(self):
        # "não funciona" contem "funciona" (positivo) mas e negacao
        self.assertEqual(classify_sentiment("O app não funciona, erro direto"), "negativo")

    def test_neutro_sem_palavras(self):
        self.assertEqual(classify_sentiment("Aplicativo de banco"), "neutro")

    def test_estrelas_altas_puxam_positivo(self):
        self.assertEqual(classify_sentiment("App comum", "5"), "positivo")

    def test_estrelas_baixas_puxam_negativo(self):
        self.assertEqual(classify_sentiment("App comum", "1"), "negativo")

    def test_estrelas_e_lexico_empatam_vira_neutro(self):
        # lexico positivo (+1) mas 1 estrela (-1): 0 -> neutro
        self.assertEqual(classify_sentiment("ótimo", "1"), "neutro")

    def test_estrelas_reforcam_negativo(self):
        # "erro" (-1) + 1 estrela (-1): -2 -> negativo
        self.assertEqual(classify_sentiment("erro", "1"), "negativo")


class TestClassifyIntents(unittest.TestCase):
    def test_elogio(self):
        self.assertIn("elogio", classify_intents("Ótimo app, recomendo demais!"))

    def test_problema_tecnico(self):
        self.assertIn("problema_tecnico", classify_intents("O app trava toda hora"))

    def test_cobranca_e_reembolso(self):
        intents = classify_intents("Cobraram duas vezes, quero reembolso")
        self.assertIn("cobranca_indevida", intents)
        self.assertIn("reembolso", intents)

    def test_negacao_nao_gera_intencao_positiva(self):
        intents = classify_intents("O app não funciona, erro toda hora")
        self.assertNotIn("experiencia_positiva", intents)
        self.assertNotIn("elogio", intents)
        self.assertIn("problema_tecnico", intents)

    def test_maximo_tres_intencoes(self):
        intents = classify_intents("trava, erro, bug, cobrança, péssimo atendimento, demora")
        self.assertLessEqual(len(intents), 3)

    def test_vazio(self):
        self.assertEqual(classify_intents(""), [])


if __name__ == "__main__":
    unittest.main()