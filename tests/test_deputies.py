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

    def test_ambiguous_and_unmatched_on_low_margin_or_score(self):
        extraction = {
            "deputies": [
                {
                    "dataset_name": "Ana Silva",
                    "normalized_name": "ANA SILVA",
                    "parties": ["PT"],
                    "ufs": ["CE"],
                    "hearing_ids": [1],
                    "hearing_count": 1,
                    "opinion_count": 1,
                    "sources": ["lds"],
                    "cargos": ["Deputada (PT-CE)"],
                },
                {
                    "dataset_name": "Bruno Costa",
                    "normalized_name": "BRUNO COSTA",
                    "parties": ["ABC"],
                    "ufs": ["SP"],
                    "hearing_ids": [1],
                    "hearing_count": 1,
                    "opinion_count": 1,
                    "sources": ["lds"],
                    "cargos": ["Deputado (ABC-SP)"],
                },
                {
                    "dataset_name": "Carlos Ninguem",
                    "normalized_name": "CARLOS NINGUEM",
                    "parties": ["XYZ"],
                    "ufs": ["RJ"],
                    "hearing_ids": [1],
                    "hearing_count": 1,
                    "opinion_count": 1,
                    "sources": ["lds"],
                    "cargos": ["Deputado (XYZ-RJ)"],
                },
            ]
        }

        class LowMarginClient:
            def search_deputies(self, name, legislature=None):
                if name == "Ana Silva":
                    # two identical high-score candidates -> margin 0 <0.05 -> ambiguous
                    return [
                        {"id": 1, "nome": "Ana Silva", "siglaPartido": "PT", "siglaUf": "CE"},
                        {"id": 2, "nome": "Ana Silva", "siglaPartido": "PT", "siglaUf": "CE"},
                    ]
                if name == "Bruno Costa":
                    # one low-score candidate -> score <0.86 -> ambiguous
                    return [
                        {"id": 3, "nome": "Xyz Desconhecido", "siglaPartido": "QQQ", "siglaUf": "AA"},
                    ]
                # Carlos -> no candidates -> unmatched
                return []

        result = resolve_deputies(extraction, LowMarginClient(), legislature=57)
        by_name = {d["dataset_name"]: d for d in result["deputies"]}
        self.assertEqual(by_name["Ana Silva"]["resolution_status"], "ambiguous")
        self.assertIsNone(by_name["Ana Silva"]["camara"])
        self.assertEqual(by_name["Bruno Costa"]["resolution_status"], "ambiguous")
        self.assertIsNone(by_name["Bruno Costa"]["camara"])
        self.assertEqual(by_name["Carlos Ninguem"]["resolution_status"], "unmatched")
        self.assertIsNone(by_name["Carlos Ninguem"]["camara"])
        self.assertEqual(result["status_counts"]["ambiguous"], 2)
        self.assertEqual(result["status_counts"]["unmatched"], 1)

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

