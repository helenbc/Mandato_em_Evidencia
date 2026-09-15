import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.io_utils import write_json, write_jsonl
from ideias_em_rede.web_export import export_dashboard_data


def _resolution(deputies):
    return {"deputies": deputies}


def _matched_deputy(deputy_id, nome, party="ABC", uf="CE", hearing_count=2, opinion_count=3):
    return {
        "resolution_status": "matched",
        "hearing_count": hearing_count,
        "opinion_count": opinion_count,
        "camara": {"id": deputy_id, "nome": nome, "siglaPartido": party, "siglaUf": uf, "urlFoto": "http://foto"},
    }


def _ambiguous_deputy(deputy_id, nome):
    return {
        "resolution_status": "ambiguous",
        "camara": {"id": deputy_id, "nome": nome, "siglaPartido": "XYZ", "siglaUf": "SP", "urlFoto": ""},
    }


class WebExportTests(unittest.TestCase):
    def test_empty_processed_dir_returns_empty_dashboard(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"
            processed.mkdir()
            output = Path(directory) / "dashboard.json"
            dashboard = export_dashboard_data(processed, output)
            self.assertEqual(dashboard["deputies"], [])
            self.assertEqual(dashboard["llmStatus"], "awaiting_api_key")
            self.assertEqual(dashboard["stats"]["deputies"], 0)
            self.assertTrue(output.is_file())
            # file was written atomically and contains same data
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["deputies"], [])

    def test_pending_llm_when_only_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"
            (processed / "analysis").mkdir(parents=True)
            write_json(processed / "deputados_resolvidos.json", _resolution([
                _matched_deputy(7, "Bravo"),
                _matched_deputy(8, "Alpha"),
            ]))
            write_jsonl(processed / "analysis/posicoes_candidatas.jsonl", [
                {"deputado_id": 7, "subject": "S", "opinion": "Op B", "hearing_id": 1},
                {"deputado_id": 8, "subject": "S2", "opinion": "Op A", "hearing_id": 2},
            ])
            output = Path(directory) / "dashboard.json"
            dashboard = export_dashboard_data(processed, output)
            self.assertEqual(dashboard["llmStatus"], "awaiting_api_key")
            # only matched deputies, sorted by name
            self.assertEqual([d["name"] for d in dashboard["deputies"]], ["Alpha", "Bravo"])
            alpha = [d for d in dashboard["deputies"] if d["name"] == "Alpha"][0]
            self.assertEqual(alpha["speeches"][0]["status"], "pending_llm")
            self.assertEqual(alpha["speeches"][0]["stance"], "NAO_CLASSIFICADO")
            self.assertIsNone(alpha["speeches"][0]["topic"])

    def test_ready_when_positions_present(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"
            (processed / "analysis").mkdir(parents=True)
            write_json(processed / "deputados_resolvidos.json", _resolution([
                _matched_deputy(7, "Deputado Teste"),
            ]))
            write_jsonl(processed / "analysis/posicoes_llm.jsonl", [
                {
                    "deputado_id": 7,
                    "extraction_status": "ok",
                    "subject": "S",
                    "topic": "Reforma",
                    "question": "Q?",
                    "stance": "FAVORAVEL",
                    "evidence_quote": "ev",
                    "confidence": 0.9,
                    "hearing_id": 7,
                    "model": "gpt-5-mini",
                }
            ])
            output = Path(directory) / "dashboard.json"
            dashboard = export_dashboard_data(processed, output)
            self.assertEqual(dashboard["llmStatus"], "ready")
            self.assertEqual(dashboard["stats"]["classifiedSpeeches"], 1)
            speech = dashboard["deputies"][0]["speeches"][0]
            self.assertEqual(speech["status"], "ok")
            self.assertEqual(speech["topic"], "Reforma")
            self.assertEqual(speech["stance"], "FAVORAVEL")

    def test_ignores_non_matched_and_sorts(self):
        with tempfile.TemporaryDirectory() as directory:
            processed = Path(directory) / "processed"
            (processed / "analysis").mkdir(parents=True)
            write_json(processed / "deputados_resolvidos.json", _resolution([
                _matched_deputy(9, "Zeta"),
                _ambiguous_deputy(10, "Ignored"),
                _matched_deputy(11, "Alpha"),
            ]))
            output = Path(directory) / "dashboard.json"
            dashboard = export_dashboard_data(processed, output)
            self.assertEqual(len(dashboard["deputies"]), 2)
            self.assertEqual([d["name"] for d in dashboard["deputies"]], ["Alpha", "Zeta"])
            self.assertNotIn("Ignored", [d["name"] for d in dashboard["deputies"]])


if __name__ == "__main__":
    unittest.main()
