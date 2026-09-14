"""Testes offline para a CLI (src/ideias_em_rede/cli.py). Sem rede."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


# Permite rodar com PYTHONPATH=src
from ideias_em_rede.cli import DEFAULT_DATASET, DEFAULT_PROCESSED, build_parser, main


PUBLIC_DATASET = Path("PublicHearingBR")
# fallback quando teste é executado de diretório diferente: tenta resolver relativo ao arquivo
if not PUBLIC_DATASET.is_dir():
    PUBLIC_DATASET = Path(__file__).resolve().parents[1] / "PublicHearingBR"


def _write_minimal_fake_dataset(base: Path) -> None:
    """Cria par LDS/NLI mínimo válido em base para audit offline."""
    lds_record = {
        "id": 1,
        "materia": "Matéria fake",
        "transcricao": "Transcrição fake",
        "metadados": {
            "assunto": "Tema fake",
            "envolvidos": [
                {
                    "nome": "Ana Silva",
                    "cargo": "Deputada Federal (ABC-SP)",
                    "opinioes": ["Opinião 1"],
                }
            ],
        },
    }
    nli_record = {
        "id": 1,
        "metadados_extraidos": {
            "assunto": "Tema fake",
            "envolvidos": [
                {
                    "nome": "Ana Silva",
                    "cargo": "Deputada Federal (ABC-SP)",
                    "opinioes": [
                        {
                            "opiniao": "Opinião 1",
                            "chunks_proximos": ["1", "2", "3", "4"],
                            "verificacao_alucinacao": {"verificacao_manual": False},
                        }
                    ],
                }
            ],
        },
    }
    (base / "PublicHearingBR_LDS.jsonl").write_text(
        json.dumps(lds_record, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (base / "PublicHearingBR_NLI.jsonl").write_text(
        json.dumps(nli_record, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class CliParserDefaultsTests(unittest.TestCase):
    def test_build_parser_defaults(self):
        # constante central
        self.assertEqual(DEFAULT_PROCESSED, Path("data/processed"))
        self.assertEqual(DEFAULT_DATASET, Path("PublicHearingBR"))

        parser = build_parser()

        # audit defaults
        audit_args = parser.parse_args(["audit"])
        self.assertEqual(audit_args.dataset_dir, Path("PublicHearingBR"))
        self.assertEqual(audit_args.dataset_dir, DEFAULT_DATASET)

        # extract defaults
        extract_args = parser.parse_args(["extract"])
        self.assertEqual(extract_args.source, "lds")
        self.assertIsNone(extract_args.limit)
        self.assertEqual(extract_args.dataset_dir, Path("PublicHearingBR"))
        self.assertEqual(
            extract_args.output, DEFAULT_PROCESSED / "deputados_extraidos.json"
        )

        # web-data defaults
        web_args = parser.parse_args(["web-data"])
        self.assertEqual(web_args.processed_dir, DEFAULT_PROCESSED)
        self.assertEqual(web_args.output, Path("web/app/dashboard.json"))

        # alignment defaults (verifica que parser existe e não exige rede)
        align_args = parser.parse_args(["alignment"])
        self.assertEqual(align_args.votes, Path("data/processed/camara/votos.jsonl"))
        self.assertEqual(
            align_args.orientations, Path("data/processed/camara/orientacoes.jsonl")
        )
        self.assertEqual(align_args.votings, Path("data/processed/camara/votacoes.jsonl"))
        self.assertEqual(align_args.output_dir, Path("data/processed/analysis"))


class CliOfflineTests(unittest.TestCase):
    def test_audit_offline_fake_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write_minimal_fake_dataset(base)
            # usa patch para isolar e capturar saída sem tocar stdout global
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                # não deve levantar
                main(["audit", "--dataset-dir", str(base)])
                output = fake_out.getvalue()

            self.assertTrue(output.strip(), "audit deveria imprimir JSON no stdout")
            parsed = json.loads(output)
            # estrutura de audit_dataset
            self.assertIn("lds", parsed)
            self.assertIn("nli", parsed)
            self.assertIn("ids_coincidem", parsed)
            self.assertEqual(parsed["lds"]["audiencias"], 1)
            self.assertEqual(parsed["nli"]["audiencias"], 1)
            self.assertTrue(parsed["ids_coincidem"])

    def test_extract_offline_creates_file(self):
        # usa dataset real PublicHearingBR local, sem rede, com limit pequeno
        if not PUBLIC_DATASET.is_dir():
            self.skipTest(f"dataset real não encontrado em {PUBLIC_DATASET}")
        # garante que os dois arquivos existem
        if not (PUBLIC_DATASET / "PublicHearingBR_LDS.jsonl").is_file():
            self.skipTest("PublicHearingBR_LDS.jsonl ausente")

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.json"
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main(
                    [
                        "extract",
                        "--dataset-dir",
                        str(PUBLIC_DATASET),
                        "--source",
                        "lds",
                        "--limit",
                        "2",
                        "--output",
                        str(out),
                    ]
                )
                stdout = fake_out.getvalue()

            self.assertTrue(out.is_file(), "extract deveria criar o arquivo de saída")
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("total_deputies", data)
            self.assertIn("deputies", data)
            self.assertLessEqual(data["total_deputies"], 2)
            self.assertEqual(len(data["deputies"]), data["total_deputies"])
            self.assertEqual(data["source"], "lds")
            # stdout também deve ser JSON com output e total_deputies
            printed = json.loads(stdout)
            self.assertEqual(printed["output"], str(out))
            self.assertEqual(printed["total_deputies"], data["total_deputies"])

    def test_web_data_empty_processed_via_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            processed = Path(tmp) / "processed"
            processed.mkdir()
            out = Path(tmp) / "dashboard.json"
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                main(["web-data", "--processed-dir", str(processed), "--output", str(out)])
                stdout = fake_out.getvalue()

            self.assertTrue(out.is_file(), "web-data deveria criar dashboard.json mesmo com processed vazio")
            dashboard = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(dashboard["deputies"], [])
            self.assertEqual(dashboard["llmStatus"], "awaiting_api_key")
            self.assertEqual(dashboard["stats"]["deputies"], 0)

            printed = json.loads(stdout)
            self.assertEqual(printed["output"], str(out))
            self.assertEqual(printed["deputies"], 0)
            self.assertEqual(printed["llm_status"], "awaiting_api_key")

    def test_alignment_help_or_parse(self):
        # parse_args funciona offline
        parser = build_parser()
        args = parser.parse_args(["alignment", "--votes", "a.jsonl"])
        self.assertEqual(args.votes, Path("a.jsonl"))
        # --help deve sair com código 0 via main (argparse)
        with patch("sys.stdout", new=io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main(["alignment", "--help"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
