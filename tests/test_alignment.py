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

    def test_majority_fallback_aligned(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7)},
        ]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
            self._bench_vote("v1", 9, "ABC", "Sim"),
            self._bench_vote("v1", 10, "ABC", "Não"),
        ]
        details, summary = compute_party_alignment(votes, [], [], bench_votes=bench)
        self.assertEqual(details[0]["status"], "aligned")
        self.assertEqual(details[0]["orientacao"], "SIM")
        self.assertEqual(details[0]["orientacao_fonte"], "MAIORIA_ABC")
        deputy = summary["deputies"][0]
        self.assertEqual(deputy["majority_fallback_votes"], 1)
        self.assertEqual(deputy["alignment_score"], 1.0)
        self.assertEqual(deputy["coverage"], 1.0)

    def test_majority_fallback_diverged(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Não", "deputado_": self._named_deputy(7)},
        ]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Não"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
            self._bench_vote("v1", 9, "ABC", "Sim"),
        ]
        details, _ = compute_party_alignment(votes, [], [], bench_votes=bench)
        self.assertEqual(details[0]["status"], "diverged")
        self.assertEqual(details[0]["orientacao_fonte"], "MAIORIA_ABC")

    def test_majority_tie_keeps_no_orientation(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7)},
        ]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
            self._bench_vote("v1", 9, "ABC", "Não"),
        ]
        details, summary = compute_party_alignment(votes, [], [], bench_votes=bench)
        self.assertEqual(details[0]["status"], "no_orientation")
        self.assertIsNone(summary["deputies"][0]["alignment_score"])

    def test_majority_requires_quorum(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7)},
        ]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
        ]
        details, _ = compute_party_alignment(votes, [], [], bench_votes=bench)
        self.assertEqual(details[0]["status"], "no_orientation")

    def test_deputy_excluded_from_majority(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7)},
        ]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
            self._bench_vote("v1", 9, "ABC", "Não"),
            self._bench_vote("v1", 10, "ABC", "Não"),
        ]
        details, _ = compute_party_alignment(votes, [], [], bench_votes=bench)
        # Sem leave-one-out seria empate (2x2); excluindo o avaliado, dá NAO.
        self.assertEqual(details[0]["status"], "diverged")
        self.assertEqual(details[0]["orientacao"], "NAO")

    def test_orientation_prevails_over_majority(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7)},
        ]
        orientations = [self._orientation("v1", "Não")]
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Sim"),
            self._bench_vote("v1", 9, "ABC", "Sim"),
        ]
        details, _ = compute_party_alignment(votes, orientations, [], bench_votes=bench)
        # Orientação Não x maioria Sim: deputado votou Sim, com a maioria e
        # contra a orientação -> vale a orientação oficial: diverged.
        self.assertEqual(details[0]["status"], "diverged")
        self.assertEqual(details[0]["orientacao"], "NAO")
        self.assertEqual(details[0]["orientacao_fonte"], "ABC")

    @staticmethod
    def _named_deputy(deputy_id, party="ABC"):
        return {
            "id": deputy_id,
            "nome": f"Deputado {deputy_id}",
            "siglaPartido": party,
            "siglaUf": "CE",
        }

    @staticmethod
    def _bench_vote(voting_id, deputy_id, party, value):
        return {
            "votacao_id": voting_id,
            "tipoVoto": value,
            "deputado_": {
                "id": deputy_id,
                "nome": f"Deputado {deputy_id}",
                "siglaPartido": party,
                "siglaUf": "CE",
            },
        }

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
