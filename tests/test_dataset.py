import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.dataset import DatasetPaths, audit_dataset


class DatasetTests(unittest.TestCase):
    def test_audit_counts_nested_opinions(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            lds = {
                "id": 1,
                "materia": "Resumo",
                "transcricao": "Texto",
                "metadados": {
                    "assunto": "Tema",
                    "envolvidos": [
                        {"nome": "Ana", "cargo": "Deputada (ABC-SP)", "opinioes": ["A", "B"]}
                    ],
                },
            }
            nli = {
                "id": 1,
                "metadados_extraidos": {
                    "assunto": "Tema",
                    "envolvidos": [
                        {
                            "nome": "Ana",
                            "cargo": "Deputada (ABC-SP)",
                            "opinioes": [
                                {
                                    "opiniao": "A",
                                    "chunks_proximos": ["1", "2", "3", "4"],
                                    "verificacao_alucinacao": {"verificacao_manual": False},
                                }
                            ],
                        }
                    ],
                },
            }
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps(lds) + "\n", encoding="utf-8"
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps(nli) + "\n", encoding="utf-8"
            )
            result = audit_dataset(DatasetPaths(base))
            self.assertEqual(result["lds"]["opinioes"], 2)
            self.assertEqual(result["nli"]["opinioes"], 1)
            self.assertTrue(result["ids_coincidem"])


if __name__ == "__main__":
    unittest.main()

