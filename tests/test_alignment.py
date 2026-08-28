import unittest

from ideias_em_rede.alignment import compute_party_alignment, resolve_orientation


class AlignmentTests(unittest.TestCase):
    def test_resolves_direct_party_and_formal_federation(self):
        orientations = [
            {
                "codTipoLideranca": "P",
                "siglaPartidoBloco": "NOVO",
                "orientacaoVoto": "Não",
            },
            {
                "codTipoLideranca": "F",
                "siglaPartidoBloco": "Fdr PT-PCdoB-PV",
                "orientacaoVoto": "Sim",
            },
        ]
        self.assertEqual(resolve_orientation("NOVO", orientations)[:2], ("found", "NAO"))
        self.assertEqual(resolve_orientation("PT", orientations)[:2], ("found", "SIM"))

    def test_score_uses_only_comparable_votes(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._deputy()},
            {"votacao_id": "v2", "tipoVoto": "Não", "deputado_": self._deputy()},
            {"votacao_id": "v3", "tipoVoto": "Sim", "deputado_": self._deputy()},
        ]
        orientations = [
            self._orientation("v1", "Sim"),
            self._orientation("v2", "Sim"),
            self._orientation("v3", "Liberado"),
        ]
        details, summary = compute_party_alignment(votes, orientations, [])
        self.assertEqual([row["status"] for row in details], ["aligned", "diverged", "released"])
        deputy = summary["deputies"][0]
        self.assertEqual(deputy["comparable_votes"], 2)
        self.assertEqual(deputy["alignment_score"], 0.5)
        self.assertEqual(deputy["coverage"], 0.6667)

    @staticmethod
    def _deputy():
        return {"id": 7, "nome": "Deputada Teste", "siglaPartido": "ABC", "siglaUf": "CE"}

    @staticmethod
    def _orientation(voting_id, value):
        return {
            "votacao_id": voting_id,
            "codTipoLideranca": "P",
            "siglaPartidoBloco": "ABC",
            "orientacaoVoto": value,
        }


if __name__ == "__main__":
    unittest.main()
