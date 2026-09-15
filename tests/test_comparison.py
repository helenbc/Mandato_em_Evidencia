import unittest

from ideias_em_rede.comparison import compare_speeches_and_votes


class ComparisonTests(unittest.TestCase):
    def test_divergente(self):
        positions = [
            {
                "candidate_id": "c1",
                "deputado_id": 9,
                "deputado_nome": "Ana",
                "partido": "ABC",
                "subject": "Reforma tributária",
                "topic": "Reforma tributária",
                "question": "É favorável?",
                "opinion": "Sou contra a proposta",
                "stance": "CONTRARIO",
                "evidence_quote": "Sou contra",
                "confidence": 0.9,
                "extraction_status": "ok",
            }
        ]
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": {"id": 9}},
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
        self.assertEqual(comparisons[0]["resultado"], "DIVERGENTE")
        self.assertEqual(comparisons[0]["posicao_fala"], "CONTRARIO")
        self.assertEqual(comparisons[0]["posicao_voto"], "FAVORAVEL")
        self.assertEqual(summary["counts"]["DIVERGENTE"], 1)

    def test_inconclusivo_misto_nao_determinado_e_abstencao(self):
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
        voting_meta = [{"id": "v1", "descricao": "Votação"}]
        # MISTO -> inconclusivo
        positions_misto = [
            {
                "candidate_id": "c1",
                "deputado_id": 9,
                "deputado_nome": "Ana",
                "partido": "ABC",
                "subject": "Reforma tributária",
                "topic": "Reforma tributária",
                "question": "É favorável?",
                "opinion": "Misto",
                "stance": "MISTO",
                "evidence_quote": "ev",
                "confidence": 0.8,
                "extraction_status": "ok",
            }
        ]
        votes_sim = [{"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": {"id": 9}}]
        comparisons, _ = compare_speeches_and_votes(positions_misto, votes_sim, voting_meta, config)
        self.assertEqual(comparisons[0]["resultado"], "INCONCLUSIVO")

        # NAO_DETERMINADO -> inconclusivo
        positions_nd = [
            {
                "candidate_id": "c2",
                "deputado_id": 9,
                "deputado_nome": "Ana",
                "partido": "ABC",
                "subject": "Reforma tributária",
                "topic": "Reforma tributária",
                "question": "É favorável?",
                "opinion": "Indefinido",
                "stance": "NAO_DETERMINADO",
                "evidence_quote": "ev",
                "confidence": 0.5,
                "extraction_status": "ok",
            }
        ]
        comparisons, _ = compare_speeches_and_votes(positions_nd, votes_sim, voting_meta, config)
        self.assertEqual(comparisons[0]["resultado"], "INCONCLUSIVO")

        # voto ABSTENCAO -> vote_stance NAO_DETERMINADO -> inconclusivo mesmo com fala FAVORAVEL
        positions_fav = [
            {
                "candidate_id": "c3",
                "deputado_id": 9,
                "deputado_nome": "Ana",
                "partido": "ABC",
                "subject": "Reforma tributária",
                "topic": "Reforma tributária",
                "question": "É favorável?",
                "opinion": "Favorável",
                "stance": "FAVORAVEL",
                "evidence_quote": "ev",
                "confidence": 0.9,
                "extraction_status": "ok",
            }
        ]
        votes_abst = [{"votacao_id": "v1", "tipoVoto": "Abstenção", "deputado_": {"id": 9}}]
        comparisons, _ = compare_speeches_and_votes(positions_fav, votes_abst, voting_meta, config)
        self.assertEqual(comparisons[0]["resultado"], "INCONCLUSIVO")
        self.assertEqual(comparisons[0]["posicao_voto"], "NAO_DETERMINADO")

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
