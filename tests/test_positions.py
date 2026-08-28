import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.dataset import DatasetPaths
from ideias_em_rede.positions import prepare_position_candidates, run_position_extraction


class FakeClassifier:
    model = "fake-test-model"

    def __init__(self, evidence):
        self.evidence = evidence

    def classify(self, candidate):
        return {
            "topic": "Reforma tributária",
            "question": "É favorável à regulamentação?",
            "stance": "FAVORAVEL",
            "evidence_quote": self.evidence,
            "rationale": "Teste",
            "confidence": 0.9,
        }


class PositionTests(unittest.TestCase):
    def test_prepares_only_verified_matched_speeches(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            nli = {
                "id": 7,
                "metadados_extraidos": {
                    "assunto": "Reforma tributária",
                    "envolvidos": [
                        {
                            "nome": "Ana Silva",
                            "opinioes": [
                                {
                                    "opiniao": "Defendeu a regulamentação.",
                                    "chunks_proximos": ["A regulamentação é necessária."],
                                    "verificacao_alucinacao": {"verificacao_manual": False},
                                },
                                {
                                    "opiniao": "Não verificada.",
                                    "chunks_proximos": ["Trecho"],
                                    "verificacao_alucinacao": {"verificacao_manual": True},
                                },
                            ],
                        }
                    ],
                },
            }
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps(nli, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            resolution = {
                "deputies": [
                    {
                        "normalized_name": "ANA SILVA",
                        "resolution_status": "matched",
                        "camara": {
                            "id": 42,
                            "nome": "Ana Silva",
                            "siglaPartido": "ABC",
                            "siglaUf": "CE",
                        },
                    }
                ]
            }
            rows = prepare_position_candidates(DatasetPaths(base), resolution)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["candidate_id"], "phbr:7:42:1")

    def test_invalid_quote_is_not_accepted_as_evidence(self):
        candidate = {
            "candidate_id": "c1",
            "subject": "Tema",
            "deputado_id": 42,
            "deputado_nome": "Ana",
            "chunks": ["Este é o texto original."],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "positions.jsonl"
            result = run_position_extraction(
                [candidate], FakeClassifier("Citação inventada"), output
            )
            row = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["invalid_evidence"], 1)
            self.assertEqual(row["stance"], "NAO_DETERMINADO")
            self.assertEqual(row["confidence"], 0)


if __name__ == "__main__":
    unittest.main()
