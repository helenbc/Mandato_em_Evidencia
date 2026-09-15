import json
import tempfile
import unittest
from pathlib import Path

from ideias_em_rede.alignment import (
    _bench_index,
    compute_party_alignment,
    resolve_orientation,
    run_party_alignment,
)
from ideias_em_rede.io_utils import write_jsonl


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

    def test_bench_index_ignores_non_comparable(self):
        bench = [
            self._bench_vote("v1", 7, "ABC", "Sim"),
            self._bench_vote("v1", 8, "ABC", "Não"),
            self._bench_vote("v1", 9, "ABC", "Artigo 17"),
            self._bench_vote("v1", 10, "ABC", "Liberado"),
        ]
        index = _bench_index(bench)
        key = ("v1", "ABC")
        self.assertIn(key, index)
        values = {value for _, value in index[key]}
        self.assertEqual(values, {"SIM", "NAO"})
        self.assertEqual(len(index[key]), 2)
        # Apenas votos não comparáveis não geram entrada
        bench_only_ignored = [
            self._bench_vote("v2", 11, "ABC", "Artigo 17"),
            self._bench_vote("v2", 12, "ABC", "Liberado"),
        ]
        index2 = _bench_index(bench_only_ignored)
        self.assertNotIn(("v2", "ABC"), index2)

    def test_run_party_alignment_auto_discovers_bench(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "input"
            output_dir = base / "output"
            input_dir.mkdir(parents=True)
            output_dir.mkdir(parents=True)
            votes_path = input_dir / "votos.jsonl"
            orientations_path = input_dir / "orientacoes.jsonl"
            votings_path = input_dir / "votacoes.jsonl"
            bench_path = input_dir / "votos_completos.jsonl"
            # votação mínima
            write_jsonl(votings_path, [{"id": "v1"}])
            write_jsonl(
                votes_path,
                [
                    {
                        "votacao_id": "v1",
                        "tipoVoto": "Sim",
                        "deputado_": self._named_deputy(7, "ABC"),
                    }
                ],
            )
            write_jsonl(orientations_path, [])
            write_jsonl(
                bench_path,
                [
                    self._bench_vote("v1", 7, "ABC", "Sim"),
                    self._bench_vote("v1", 8, "ABC", "Sim"),
                    self._bench_vote("v1", 9, "ABC", "Sim"),
                ],
            )
            summary = run_party_alignment(
                votes_path, orientations_path, votings_path, output_dir
            )
            details_path = output_dir / "alinhamento_detalhes.jsonl"
            details = [
                json.loads(line)
                for line in details_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(details), 1)
            self.assertEqual(details[0]["status"], "aligned")
            self.assertEqual(details[0]["orientacao"], "SIM")
            self.assertEqual(details[0]["orientacao_fonte"], "MAIORIA_ABC")
            self.assertEqual(summary["totals"]["majority_fallback_votes"], 1)

            # sem votos_completos -> sem fallback
            bench_path.unlink()
            output_dir2 = base / "output2"
            output_dir2.mkdir(parents=True)
            summary2 = run_party_alignment(
                votes_path, orientations_path, votings_path, output_dir2
            )
            details2 = [
                json.loads(line)
                for line in (output_dir2 / "alinhamento_detalhes.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(details2[0]["status"], "no_orientation")
            self.assertIsNone(details2[0]["orientacao"])
            self.assertEqual(summary2["totals"]["majority_fallback_votes"], 0)

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
