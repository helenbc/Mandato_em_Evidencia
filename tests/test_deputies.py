import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.dataset import DatasetPaths
from ideias_em_rede.deputies import extract_deputies, parse_deputy_cargo, resolve_deputies


class FakeClient:
    def search_deputies(self, name, legislature=None):
        return [
            {
                "id": 123,
                "nome": "Maria da Silva",
                "siglaPartido": "PT",
                "siglaUf": "CE",
                "idLegislatura": legislature,
            }
        ]


class DeputyTests(unittest.TestCase):
    def test_parse_cargo(self):
        self.assertEqual(
            parse_deputy_cargo("Deputado Federal (Bloco/PT - RN)"),
            {"party": "PT", "uf": "RN"},
        )
        self.assertIsNone(parse_deputy_cargo("Jornalista"))

    def test_extract_and_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            lds = {
                "id": 1,
                "materia": "Resumo",
                "transcricao": "Texto",
                "metadados": {
                    "assunto": "Tema",
                    "envolvidos": [
                        {
                            "nome": "Maria da Silva",
                            "cargo": "Deputada (PT-CE)",
                            "opinioes": ["A", "B"],
                        },
                        {"nome": "Joao", "cargo": "Jornalista", "opinioes": ["C"]},
                    ],
                },
            }
            nli = {
                "id": 1,
                "metadados_extraidos": {"assunto": "Tema", "envolvidos": []},
            }
            (base / "PublicHearingBR_LDS.jsonl").write_text(
                json.dumps(lds) + "\n", encoding="utf-8"
            )
            (base / "PublicHearingBR_NLI.jsonl").write_text(
                json.dumps(nli) + "\n", encoding="utf-8"
            )
            extraction = extract_deputies(DatasetPaths(base))
            self.assertEqual(extraction["total_deputies"], 1)
            self.assertEqual(extraction["deputies"][0]["opinion_count"], 2)
            resolution = resolve_deputies(extraction, FakeClient())
            self.assertEqual(resolution["status_counts"], {"matched": 1})
            self.assertEqual(resolution["deputies"][0]["camara"]["id"], 123)


if __name__ == "__main__":
    unittest.main()

