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
    def test_prepare_position_candidates_filters_per_deputy_limit_hearing_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            # hearing 1: Ana 2 opinions, Bruno 1 opinion
            # hearing 2: Ana 1 opinion
            # hearing 3: Bruno 1 opinion
            def _opinion(text, chunks=None):
                return {
                    "opiniao": text,
                    "chunks_proximos": chunks or [f"chunk {text}"],
                    "verificacao_alucinacao": {"verificacao_manual": False},
                }

            nli_records = [
                {
                    "id": 1,
                    "metadados_extraidos": {
                        "assunto": "Tema 1",
                        "envolvidos": [
                            {"nome": "Ana Silva", "opinioes": [_opinion("A1"), _opinion("A2")]},
                            {"nome": "Bruno Costa", "opinioes": [_opinion("B1")]},
                        ],
                    },
                },
                {
                    "id": 2,
                    "metadados_extraidos": {
                        "assunto": "Tema 2",
                        "envolvidos": [
                            {"nome": "Ana Silva", "opinioes": [_opinion("A3")]},
                        ],
                    },
                },
                {
                    "id": 3,
                    "metadados_extraidos": {
                        "assunto": "Tema 3",
                        "envolvidos": [
                            {"nome": "Bruno Costa", "opinioes": [_opinion("B2")]},
                        ],
                    },
                },
            ]
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in nli_records) + "\n",
                encoding="utf-8",
            )
            resolution = {
                "deputies": [
                    {
                        "normalized_name": "ANA SILVA",
                        "resolution_status": "matched",
                        "camara": {"id": 42, "nome": "Ana Silva", "siglaPartido": "ABC", "siglaUf": "CE"},
                    },
                    {
                        "normalized_name": "BRUNO COSTA",
                        "resolution_status": "matched",
                        "camara": {"id": 43, "nome": "Bruno Costa", "siglaPartido": "XYZ", "siglaUf": "SP"},
                    },
                ]
            }
            # per_deputy=1 -> at most 1 per deputy (total 2)
            rows = prepare_position_candidates(DatasetPaths(base), resolution, limit=10, per_deputy=1)
            self.assertEqual(len(rows), 2)
            # ensure each deputy appears once
            self.assertEqual({r["deputado_id"] for r in rows}, {42, 43})
            # limit=1 -> global limit
            rows_limited = prepare_position_candidates(DatasetPaths(base), resolution, limit=1, per_deputy=2)
            self.assertEqual(len(rows_limited), 1)
            # hearing_ids filter
            rows_filtered = prepare_position_candidates(
                DatasetPaths(base), resolution, limit=10, per_deputy=10, hearing_ids={2}
            )
            self.assertTrue(all(r["hearing_id"] == 2 for r in rows_filtered))
            self.assertEqual(len(rows_filtered), 1)
            self.assertEqual(rows_filtered[0]["deputado_id"], 42)

    def test_run_position_extraction_with_valid_evidence(self):
        candidate = {
            "candidate_id": "c1",
            "subject": "Tema",
            "deputado_id": 42,
            "deputado_nome": "Ana",
            "chunks": ["Este é o texto original com citação."],
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "positions.jsonl"
            result = run_position_extraction(
                [candidate], FakeClassifier("Este é o texto original com citação."), output
            )
            row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(result["valid_evidence"], 1)
            self.assertEqual(result["invalid_evidence"], 0)
            self.assertEqual(row["extraction_status"], "ok")
            self.assertTrue(row["evidence_valid"])
            self.assertEqual(row["stance"], "FAVORAVEL")
            self.assertEqual(row["confidence"], 0.9)

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
