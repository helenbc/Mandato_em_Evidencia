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


if __name__ == "__main__":
    unittest.main()

