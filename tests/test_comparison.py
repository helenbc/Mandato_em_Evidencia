import unittest

from ideias_em_rede.comparison import compare_speeches_and_votes


class ComparisonTests(unittest.TestCase):
    def test_matches_topic_deputy_and_vote(self):
        positions = [
            {
                "candidate_id": "c1",
                "deputado_id": 9,
                "deputado_nome": "Ana",
                "partido": "ABC",
                "subject": "Regulamentação da reforma tributária",
                "topic": "Reforma tributária",
                "question": "É favorável?",
                "opinion": "Defendeu a proposta",
                "stance": "FAVORAVEL",
                "evidence_quote": "Defendo a proposta",
                "confidence": 0.9,
                "extraction_status": "ok",
            }
        ]
        votes = [
            {
                "votacao_id": "v1",
                "tipoVoto": "Sim",
                "deputado_": {"id": 9},
            }
        ]
        config = {
            "description": "Amostra",
            "votings": [
                {
                    "votacao_id": "v1",
                    "question": "Aprovar?",
                    "topic_terms": ["reforma tributária"],
                    "yes_stance": "FAVORAVEL",
                    "no_stance": "CONTRARIO",
                }
            ],
        }
        comparisons, summary = compare_speeches_and_votes(
            positions, votes, [{"id": "v1", "descricao": "Votação"}], config
        )
        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0]["resultado"], "COERENTE")
        self.assertEqual(summary["counts"]["COERENTE"], 1)


if __name__ == "__main__":
    unittest.main()
