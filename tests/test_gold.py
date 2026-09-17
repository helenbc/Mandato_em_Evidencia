"""Tests para gold set humano — schema, validação e métrica.

Schema (documentado em src/ideias_em_rede/gold.py):
- cada linha JSONL deve conter candidate_id (str não vazio), stance (enum
  FAVORAVEL|CONTRARIO|MISTO|NAO_DETERMINADO) e evidence_quote (str não vazia)
- validate_gold_row levanta ValueError se inválido
- evaluate_gold casa por candidate_id, só conta matches com extraction_status=="ok",
  invalid_evidence quando != "ok", accuracy = correct/matches
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.gold import STANCES, evaluate_gold, validate_gold_row
from ideias_em_rede.cli import main
from ideias_em_rede.io_utils import write_json


class GoldSchemaTests(unittest.TestCase):
    def test_validate_rejects_invalid_stance(self):
        with self.assertRaises(ValueError) as cm:
            validate_gold_row(
                {"candidate_id": "c1", "stance": "INVALIDO", "evidence_quote": "ev"}
            )
        self.assertIn("stance", str(cm.exception).lower())

    def test_validate_rejects_empty_evidence(self):
        with self.assertRaises(ValueError) as cm:
            validate_gold_row(
                {"candidate_id": "c1", "stance": "FAVORAVEL", "evidence_quote": "  "}
            )
        self.assertIn("evidence_quote", str(cm.exception))

    def test_validate_rejects_missing_candidate_id(self):
        with self.assertRaises(ValueError) as cm:
            validate_gold_row({"stance": "FAVORAVEL", "evidence_quote": "ev"})
        self.assertIn("candidate_id", str(cm.exception))

    def test_validate_rejects_none_candidate_id(self):
        with self.assertRaises(ValueError):
            validate_gold_row(
                {"candidate_id": "", "stance": "FAVORAVEL", "evidence_quote": "ev"}
            )

    def test_validate_accepts_valid_row(self):
        row = {
            "candidate_id": "phbr:7:42:1",
            "stance": "FAVORAVEL",
            "evidence_quote": "citação literal",
        }
        # não deve levantar
        self.assertEqual(validate_gold_row(row), row)

    def test_stances_enum(self):
        self.assertEqual(STANCES, {"FAVORAVEL", "CONTRARIO", "MISTO", "NAO_DETERMINADO"})


class GoldMetricTests(unittest.TestCase):
    def test_evaluate_gold_accuracy_2_3(self):
        # 4 gold, 3 matches ok (2 acertos +1 erro) +1 invalid_evidence => accuracy 2/3
        gold_rows = [
            {"candidate_id": "c1", "stance": "FAVORAVEL", "evidence_quote": "ev1"},
            {"candidate_id": "c2", "stance": "CONTRARIO", "evidence_quote": "ev2"},
            {"candidate_id": "c3", "stance": "MISTO", "evidence_quote": "ev3"},
            {"candidate_id": "c4", "stance": "FAVORAVEL", "evidence_quote": "ev4"},
        ]
        positions = [
            {"candidate_id": "c1", "stance": "FAVORAVEL", "extraction_status": "ok"},
            {"candidate_id": "c2", "stance": "FAVORAVEL", "extraction_status": "ok"},  # erro
            {"candidate_id": "c3", "stance": "MISTO", "extraction_status": "ok"},
            {
                "candidate_id": "c4",
                "stance": "FAVORAVEL",
                "extraction_status": "invalid_evidence",
            },
        ]
        result = evaluate_gold(positions, gold_rows)
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["matches"], 3)
        self.assertEqual(result["invalid_evidence"], 1)
        self.assertEqual(result["correct"], 2)
        self.assertAlmostEqual(result["accuracy"], 2 / 3)

    def test_evaluate_gold_by_stance(self):
        gold_rows = [
            {"candidate_id": "c1", "stance": "FAVORAVEL", "evidence_quote": "ev1"},
            {"candidate_id": "c2", "stance": "FAVORAVEL", "evidence_quote": "ev2"},
            {"candidate_id": "c3", "stance": "CONTRARIO", "evidence_quote": "ev3"},
        ]
        positions = [
            {"candidate_id": "c1", "stance": "FAVORAVEL", "extraction_status": "ok"},
            {"candidate_id": "c2", "stance": "CONTRARIO", "extraction_status": "ok"},
            {"candidate_id": "c3", "stance": "CONTRARIO", "extraction_status": "ok"},
        ]
        result = evaluate_gold(positions, gold_rows)
        by = result["by_stance"]
        self.assertIn("FAVORAVEL", by)
        self.assertIn("CONTRARIO", by)
        self.assertEqual(by["FAVORAVEL"]["total"], 2)
        self.assertEqual(by["FAVORAVEL"]["matches"], 2)
        self.assertEqual(by["FAVORAVEL"]["correct"], 1)
        self.assertAlmostEqual(by["FAVORAVEL"]["accuracy"], 0.5)
        self.assertEqual(by["CONTRARIO"]["total"], 1)
        self.assertEqual(by["CONTRARIO"]["correct"], 1)

    def test_evaluate_gold_no_matches(self):
        gold_rows = [
            {"candidate_id": "c1", "stance": "FAVORAVEL", "evidence_quote": "ev1"},
        ]
        positions: list[dict] = []
        result = evaluate_gold(positions, gold_rows)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["matches"], 0)
        self.assertEqual(result["accuracy"], 0.0)


class GoldCLITests(unittest.TestCase):
    def test_cli_evaluate_gold_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            positions_path = tmp_path / "posicoes.jsonl"
            gold_path = tmp_path / "gold.jsonl"
            out_dir = tmp_path / "out"

            gold_rows = [
                {"candidate_id": "c1", "stance": "FAVORAVEL", "evidence_quote": "ev1"},
                {"candidate_id": "c2", "stance": "CONTRARIO", "evidence_quote": "ev2"},
                {"candidate_id": "c3", "stance": "MISTO", "evidence_quote": "ev3"},
                {"candidate_id": "c4", "stance": "FAVORAVEL", "evidence_quote": "ev4"},
            ]
            positions = [
                {"candidate_id": "c1", "stance": "FAVORAVEL", "extraction_status": "ok"},
                {"candidate_id": "c2", "stance": "FAVORAVEL", "extraction_status": "ok"},
                {"candidate_id": "c3", "stance": "MISTO", "extraction_status": "ok"},
                {
                    "candidate_id": "c4",
                    "stance": "FAVORAVEL",
                    "extraction_status": "invalid_evidence",
                },
            ]
            positions_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in positions) + "\n",
                encoding="utf-8",
            )
            gold_path.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in gold_rows) + "\n",
                encoding="utf-8",
            )

            main(
                [
                    "evaluate-gold",
                    "--positions",
                    str(positions_path),
                    "--gold",
                    str(gold_path),
                    "--output-dir",
                    str(out_dir),
                ]
            )

            out_file = out_dir / "gold_metricas.json"
            self.assertTrue(out_file.is_file(), "gold_metricas.json deveria ter sido criado")
            data = json.loads(out_file.read_text(encoding="utf-8"))
            self.assertEqual(data["total"], 4)
            self.assertEqual(data["matches"], 3)
            self.assertEqual(data["invalid_evidence"], 1)
            self.assertAlmostEqual(data["accuracy"], 2 / 3)
            self.assertIn("by_stance", data)

    def test_cli_evaluate_gold_missing_gold_friendly_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            positions_path = tmp_path / "pos.jsonl"
            positions_path.write_text("", encoding="utf-8")
            gold_path = tmp_path / "naoexiste.jsonl"
            out_dir = tmp_path / "out"
            with self.assertRaises(SystemExit) as cm:
                main(
                    [
                        "evaluate-gold",
                        "--positions",
                        str(positions_path),
                        "--gold",
                        str(gold_path),
                        "--output-dir",
                        str(out_dir),
                    ]
                )
            msg = str(cm.exception)
            self.assertIn("Gold set", msg)


if __name__ == "__main__":
    unittest.main()
