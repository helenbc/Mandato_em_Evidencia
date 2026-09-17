import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.pipeline import collect_votes_and_orientations, split_range


class FakeClient:
    def list_votings(self, start_date, end_date):
        yield {"id": "v1", "dataHoraRegistro": "2024-01-01T10:00:00", "siglaOrgao": "PLEN"}
        yield {"id": "v2", "dataHoraRegistro": "2024-01-02T10:00:00", "siglaOrgao": "CCJ"}

    def voting_votes(self, voting_id):
        if voting_id == "v1":
            return [
                {"deputado_": {"id": 123, "nome": "Maria"}, "tipoVoto": "Sim"},
                {"deputado_": {"id": 999, "nome": "Outro"}, "tipoVoto": "Nao"},
            ]
        return []

    def voting_orientations(self, voting_id):
        return [{"siglaBancada": "PT", "orientacaoVoto": "Sim"}]


class PipelineTests(unittest.TestCase):
    def test_rejects_inverted_dates(self):
        resolution = {
            "deputies": [
                {
                    "resolution_status": "matched",
                    "camara": {"id": 123},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                collect_votes_and_orientations(
                    resolution,
                    FakeClient(),
                    "2024-01-31",
                    "2024-01-01",
                    Path(directory),
                )

    def test_organ_filter_and_max_votings(self):
        class FilterClient:
            def list_votings(self, start_date, end_date):
                yield {"id": "v1", "dataHoraRegistro": "2024-01-01T10:00:00", "siglaOrgao": "PLEN"}
                yield {"id": "v2", "dataHoraRegistro": "2024-01-02T10:00:00", "siglaOrgao": "CCJ"}
                yield {"id": "v3", "dataHoraRegistro": "2024-01-03T10:00:00", "siglaOrgao": "PLEN"}

            def voting_votes(self, voting_id):
                return [{"deputado_": {"id": 123, "nome": "Maria"}, "tipoVoto": "Sim"}]

            def voting_orientations(self, voting_id):
                return []

        resolution = {
            "deputies": [
                {
                    "resolution_status": "matched",
                    "camara": {"id": 123},
                }
            ]
        }
        # organ filter: only PLEN
        with tempfile.TemporaryDirectory() as directory:
            summary = collect_votes_and_orientations(
                resolution,
                FilterClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                organ="PLEN",
                workers=1,
            )
            self.assertEqual(summary["listed_votings"], 2)
            self.assertEqual(summary["votings_with_selected_votes"], 2)

        # max_votings limits
        with tempfile.TemporaryDirectory() as directory:
            summary = collect_votes_and_orientations(
                resolution,
                FilterClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                max_votings=1,
                workers=1,
            )
            self.assertEqual(summary["listed_votings"], 1)
            self.assertEqual(summary["votings_with_selected_votes"], 1)

        # organ + max_votings combined
        with tempfile.TemporaryDirectory() as directory:
            summary = collect_votes_and_orientations(
                resolution,
                FilterClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                organ="PLEN",
                max_votings=1,
                workers=1,
            )
            self.assertEqual(summary["listed_votings"], 1)

    def test_writes_ordered_outputs(self):
        class OrderedClient:
            def list_votings(self, start_date, end_date):
                # out of order on purpose
                yield {"id": "v2", "dataHoraRegistro": "2024-01-02T10:00:00", "siglaOrgao": "PLEN"}
                yield {"id": "v1", "dataHoraRegistro": "2024-01-01T10:00:00", "siglaOrgao": "PLEN"}

            def voting_votes(self, voting_id):
                if voting_id == "v1":
                    # reverse deputy order
                    return [
                        {"deputado_": {"id": 999, "nome": "Z"}, "tipoVoto": "Sim"},
                        {"deputado_": {"id": 123, "nome": "A"}, "tipoVoto": "Sim"},
                    ]
                if voting_id == "v2":
                    return [{"deputado_": {"id": 123, "nome": "A"}, "tipoVoto": "Sim"}]
                return []

            def voting_orientations(self, voting_id):
                return []

        resolution = {
            "deputies": [
                {"resolution_status": "matched", "camara": {"id": 123}},
                {"resolution_status": "matched", "camara": {"id": 999}},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            collect_votes_and_orientations(
                resolution,
                OrderedClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                workers=1,
            )
            votacoes = [
                json.loads(line)
                for line in (Path(directory) / "votacoes.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            votos = [
                json.loads(line)
                for line in (Path(directory) / "votos.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            # votacoes ordered by dataHoraRegistro then id
            self.assertEqual([row["id"] for row in votacoes], ["v1", "v2"])
            # votos ordered by votacao_id then deputy id
            self.assertEqual(
                [(row["votacao_id"], row["deputado_"]["id"]) for row in votos],
                [("v1", 123), ("v1", 999), ("v2", 123)],
            )

    def test_collects_only_selected_votes(self):
        resolution = {
            "deputies": [
                {
                    "resolution_status": "matched",
                    "camara": {"id": 123},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            summary = collect_votes_and_orientations(
                resolution,
                FakeClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                workers=2,
            )
            self.assertEqual(summary["listed_votings"], 2)
            self.assertEqual(summary["votings_with_selected_votes"], 1)
            self.assertEqual(summary["selected_votes"], 1)
            self.assertEqual(summary["orientations"], 1)

    def test_collects_bench_votes_for_majority(self):
        resolution = {
            "deputies": [
                {
                    "resolution_status": "matched",
                    "camara": {"id": 123},
                }
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            summary = collect_votes_and_orientations(
                resolution,
                FakeClient(),
                "2024-01-01",
                "2024-01-31",
                Path(directory),
                workers=2,
            )
            self.assertEqual(summary["bench_votes"], 2)
            bench_path = Path(directory) / "votos_completos.jsonl"
            rows = [
                json.loads(line)
                for line in bench_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 2)
            self.assertEqual(
                {row["deputado_"]["id"] for row in rows}, {123, 999}
            )

    def test_split_range_single_day(self):
        self.assertEqual(
            split_range("2024-01-05", "2024-01-05", 3),
            [("2024-01-05", "2024-01-05")],
        )

    def test_split_range_exact_window(self):
        self.assertEqual(
            split_range("2024-01-01", "2024-01-06", 3),
            [("2024-01-01", "2024-01-03"), ("2024-01-04", "2024-01-06")],
        )

    def test_split_range_with_remainder(self):
        self.assertEqual(
            split_range("2024-01-01", "2024-01-10", 3),
            [
                ("2024-01-01", "2024-01-03"),
                ("2024-01-04", "2024-01-06"),
                ("2024-01-07", "2024-01-09"),
                ("2024-01-10", "2024-01-10"),
            ],
        )

    def test_split_range_invalid(self):
        with self.assertRaises(ValueError):
            split_range("2024-02-01", "2024-01-01", 2)
        with self.assertRaises(ValueError):
            split_range("2024-01-01", "2024-01-10", 0)
        with self.assertRaises(ValueError):
            split_range("2024-01-01", "2024-01-10", -1)

    def _read_jsonl_set(self, path: Path):
        return {
            json.dumps(json.loads(line), sort_keys=True)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    def test_collect_with_batch_days_equals_single(self):
        resolution = {
            "deputies": [{"resolution_status": "matched", "camara": {"id": 123}}]
        }
        with tempfile.TemporaryDirectory() as dir_single:
            with tempfile.TemporaryDirectory() as dir_batch:
                summary_single = collect_votes_and_orientations(
                    resolution,
                    FakeClient(),
                    "2024-01-01",
                    "2024-01-02",
                    Path(dir_single),
                    workers=1,
                )
                summary_batch = collect_votes_and_orientations(
                    resolution,
                    FakeClient(),
                    "2024-01-01",
                    "2024-01-02",
                    Path(dir_batch),
                    workers=1,
                    batch_days=1,
                )
                # mesmos contadores
                self.assertEqual(
                    summary_single["listed_votings"], summary_batch["listed_votings"]
                )
                self.assertEqual(
                    summary_single["votings_with_selected_votes"],
                    summary_batch["votings_with_selected_votes"],
                )
                self.assertEqual(
                    summary_single["selected_votes"], summary_batch["selected_votes"]
                )
                self.assertEqual(
                    summary_single["bench_votes"], summary_batch["bench_votes"]
                )
                self.assertEqual(
                    summary_single["orientations"], summary_batch["orientations"]
                )
                # mesmos arquivos (conteúdo deduplicado)
                for fname in [
                    "votacoes.jsonl",
                    "votos.jsonl",
                    "votos_completos.jsonl",
                    "orientacoes.jsonl",
                ]:
                    self.assertEqual(
                        self._read_jsonl_set(Path(dir_single) / fname),
                        self._read_jsonl_set(Path(dir_batch) / fname),
                    )
                # summary batch contém lista de batches
                self.assertIn("batches", summary_batch)
                self.assertEqual(summary_batch["batch_days"], 1)
                self.assertEqual(len(summary_batch["batches"]), 2)
                self.assertNotIn("batches", summary_single)

    def test_collect_batch_idempotence_no_duplication(self):
        resolution = {
            "deputies": [{"resolution_status": "matched", "camara": {"id": 123}}]
        }
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            collect_votes_and_orientations(
                resolution,
                FakeClient(),
                "2024-01-01",
                "2024-01-02",
                out,
                workers=1,
                batch_days=1,
            )
            first = out / "votacoes.jsonl"
            first_lines = [
                line for line in first.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            # segunda coleta no mesmo diretório, mesmo batch
            collect_votes_and_orientations(
                resolution,
                FakeClient(),
                "2024-01-01",
                "2024-01-02",
                out,
                workers=1,
                batch_days=1,
            )
            second_lines = [
                line for line in first.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            self.assertEqual(len(first_lines), len(second_lines))
            self.assertEqual(len(first_lines), 1)  # só v1 tem voto selecionado
            # conteúdo idêntico
            self.assertEqual(
                {json.loads(l)["id"] for l in first_lines},
                {json.loads(l)["id"] for l in second_lines},
            )


if __name__ == "__main__":
    unittest.main()

