import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.pipeline import collect_votes_and_orientations


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


if __name__ == "__main__":
    unittest.main()

