import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.dataset import DatasetPaths, DatasetValidationError, audit_dataset, iter_lds, iter_nli


class DatasetTests(unittest.TestCase):
    def test_invalid_json_raises_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            # valid NLI to satisfy require_files, invalid LDS
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps({"id": 1, "metadados_extraidos": {"assunto": "Tema", "envolvidos": []}}) + "\n",
                encoding="utf-8",
            )
            (base / "PublicHearingBR_LDS.jsonl").write_text("not a json\n", encoding="utf-8")
            with self.assertRaises(DatasetValidationError) as ctx:
                list(iter_lds(DatasetPaths(base)))
            self.assertIn("JSON invalido", str(ctx.exception))
            # also non-object JSON
            (base / "PublicHearingBR_LDS.jsonl").write_text("[]\n", encoding="utf-8")
            with self.assertRaises(DatasetValidationError) as ctx2:
                list(iter_lds(DatasetPaths(base)))
            self.assertIn("Era esperado um objeto", str(ctx2.exception))
            # invalid NLI JSON
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps({"id": 1, "materia": "M", "transcricao": "T", "metadados": {"assunto": "A", "envolvidos": []}}) + "\n",
                encoding="utf-8",
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text("{ invalid\n", encoding="utf-8")
            with self.assertRaises(DatasetValidationError):
                list(iter_nli(DatasetPaths(base)))

    def test_missing_field_raises_validation_error(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            # LDS missing required field 'metadados'
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps({"id": 1, "materia": "M", "transcricao": "T"}) + "\n",
                encoding="utf-8",
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps({"id": 1, "metadados_extraidos": {"assunto": "A", "envolvidos": []}}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DatasetValidationError) as ctx:
                list(iter_lds(DatasetPaths(base)))
            self.assertIn("Campos ausentes", str(ctx.exception))
            # NLI missing 'metadados_extraidos'
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps({"id": 1, "materia": "M", "transcricao": "T", "metadados": {"assunto": "A", "envolvidos": []}}) + "\n",
                encoding="utf-8",
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
            with self.assertRaises(DatasetValidationError):
                list(iter_nli(DatasetPaths(base)))
            # audit_dataset also propagates
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps({"id": 1}) + "\n", encoding="utf-8"
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps({"id": 1, "metadados_extraidos": {"assunto": "A", "envolvidos": []}}) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(DatasetValidationError):
                audit_dataset(DatasetPaths(base))

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

