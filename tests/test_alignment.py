import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from ideias_em_rede.alignment import (
    _bench_index,
    _federation_map_for_date,
    _orientation_parties,
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

    def test_federation_only_within_vigency_via_resolve(self):
        orientations = [
            {
                "codTipoLideranca": "F",
                "siglaPartidoBloco": "Fdr PT-PCdoB-PV",
                "orientacaoVoto": "Sim",
            }
        ]
        self.assertEqual(resolve_orientation("PT", orientations, voting_date="2022-01-01")[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PT", orientations, voting_date="2022-06-15")[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PT", orientations, voting_date="2022-06-15T10:00:00")[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PT", orientations, voting_date=date(2022, 2, 1))[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PCDOB", orientations, voting_date="2023-01-01")[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PV", orientations, voting_date="2022-01-01")[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PT", orientations, voting_date="2021-12-31")[:2], ("no_orientation", None))
        self.assertEqual(resolve_orientation("PV", orientations, voting_date="2021-06-01")[:2], ("no_orientation", None))
        self.assertEqual(resolve_orientation("PT", orientations)[:2], ("found", "SIM"))
        self.assertEqual(resolve_orientation("PT", orientations, voting_date=None)[:2], ("found", "SIM"))
        orientations_psol = [
            {
                "codTipoLideranca": "F",
                "siglaPartidoBloco": "Fdr PSOL-REDE",
                "orientacaoVoto": "Não",
            }
        ]
        self.assertEqual(resolve_orientation("PSOL", orientations_psol, voting_date="2022-01-01")[:2], ("found", "NAO"))
        self.assertEqual(resolve_orientation("REDE", orientations_psol, voting_date="2021-06-01")[:2], ("no_orientation", None))

    def test_federation_vigency_via_compute_party_alignment(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": self._named_deputy(7, "PT")},
        ]
        orientations = [
            {
                "votacao_id": "v1",
                "codTipoLideranca": "F",
                "siglaPartidoBloco": "Fdr PT-PCdoB-PV",
                "orientacaoVoto": "Sim",
            }
        ]
        votings_before = [{"id": "v1", "data": "2021-12-31"}]
        details_before, _ = compute_party_alignment(votes, orientations, votings_before)
        self.assertEqual(details_before[0]["status"], "no_orientation")
        self.assertIsNone(details_before[0]["orientacao"])
        votings_inside = [{"id": "v1", "data": "2022-06-01"}]
        details_inside, _ = compute_party_alignment(votes, orientations, votings_inside)
        self.assertEqual(details_inside[0]["status"], "aligned")
        self.assertEqual(details_inside[0]["orientacao"], "SIM")
        votings_dt = [{"id": "v1", "dataHoraRegistro": "2022-06-01T10:00:00"}]
        details_dt, _ = compute_party_alignment(votes, orientations, votings_dt)
        self.assertEqual(details_dt[0]["status"], "aligned")

    def test_federation_fim_respected(self):
        custom = [
            {"sigla": "Fdr PT-PCdoB-PV", "membros": ["PT", "PCDOB", "PV"], "inicio": "2022-01-01", "fim": "2022-12-31"},
            {"sigla": "Fdr PSOL-REDE", "membros": ["PSOL", "REDE"], "inicio": "2022-01-01", "fim": None},
        ]
        with mock.patch("pathlib.Path.is_file", return_value=True):
            with mock.patch("pathlib.Path.read_text", return_value=json.dumps(custom)):
                orients = [
                    {"codTipoLideranca": "F", "siglaPartidoBloco": "Fdr PT-PCdoB-PV", "orientacaoVoto": "Sim"}
                ]
                self.assertEqual(resolve_orientation("PT", orients, voting_date="2022-06-01")[:2], ("found", "SIM"))
                self.assertEqual(resolve_orientation("PT", orients, voting_date="2023-01-01")[:2], ("no_orientation", None))
                orients2 = [
                    {"codTipoLideranca": "F", "siglaPartidoBloco": "Fdr PSOL-REDE", "orientacaoVoto": "Sim"}
                ]
                self.assertEqual(resolve_orientation("PSOL", orients2, voting_date="2023-06-01")[:2], ("found", "SIM"))

    def test_fallback_when_config_missing(self):
        with mock.patch("pathlib.Path.is_file", return_value=False):
            fed = _federation_map_for_date("2022-06-01")
            self.assertIn("FDR PT PCDOB PV", fed)
            self.assertIn("FDR PSOL REDE", fed)
            self.assertEqual(fed["FDR PT PCDOB PV"], {"PT", "PCDOB", "PV"})
            orients = [
                {"codTipoLideranca": "F", "siglaPartidoBloco": "Fdr PT-PCdoB-PV", "orientacaoVoto": "Sim"}
            ]
            self.assertEqual(resolve_orientation("PT", orients, voting_date="2022-06-01")[:2], ("found", "SIM"))

    def test_deputy_party_change_uses_sigla_da_epoca(self):
        votes = [
            {"votacao_id": "v1", "tipoVoto": "Sim", "deputado_": {"id": 7, "nome": "Joao", "siglaPartido": "PT", "siglaUf": "CE"}},
            {"votacao_id": "v2", "tipoVoto": "Sim", "deputado_": {"id": 7, "nome": "Joao", "siglaPartido": "PL", "siglaUf": "CE"}},
        ]
        orientations = [
            {"votacao_id": "v1", "codTipoLideranca": "P", "siglaPartidoBloco": "PT", "orientacaoVoto": "Sim"},
            {"votacao_id": "v2", "codTipoLideranca": "P", "siglaPartidoBloco": "PL", "orientacaoVoto": "Não"},
        ]
        votings = [{"id": "v1", "data": "2022-06-01"}, {"id": "v2", "data": "2022-06-02"}]
        details, summary = compute_party_alignment(votes, orientations, votings)
        by_id = {d["votacao_id"]: d for d in details}
        self.assertEqual(by_id["v1"]["status"], "aligned")
        self.assertEqual(by_id["v1"]["orientacao"], "SIM")
        self.assertEqual(by_id["v1"]["orientacao_fonte"], "PT")
        self.assertEqual(by_id["v1"]["partido"], "PT")
        self.assertEqual(by_id["v2"]["status"], "diverged")
        self.assertEqual(by_id["v2"]["orientacao"], "NAO")
        self.assertEqual(by_id["v2"]["orientacao_fonte"], "PL")
        self.assertEqual(by_id["v2"]["partido"], "PL")
        self.assertEqual(summary["deputies"][0]["comparable_votes"], 2)
        self.assertEqual(summary["deputies"][0]["aligned_votes"], 1)

    def test_party_majority_uses_sigla_da_epoca(self):
        votes_pt = [
            {"votacao_id": "v1", "tipoVoto": "Não", "deputado_": self._named_deputy(7, "PT")},
        ]
        bench = [
            self._bench_vote("v1", 7, "PT", "Não"),
            self._bench_vote("v1", 8, "PT", "Sim"),
            self._bench_vote("v1", 9, "PT", "Sim"),
            self._bench_vote("v1", 10, "PL", "Não"),
            self._bench_vote("v1", 11, "PL", "Não"),
            self._bench_vote("v1", 12, "PL", "Não"),
        ]
        details, _ = compute_party_alignment(votes_pt, [], [], bench_votes=bench)
        self.assertEqual(details[0]["orientacao"], "SIM")
        self.assertEqual(details[0]["orientacao_fonte"], "MAIORIA_PT")
        self.assertEqual(details[0]["status"], "diverged")
        votes_pl = [
            {"votacao_id": "v1", "tipoVoto": "Não", "deputado_": self._named_deputy(7, "PL")},
        ]
        details_pl, _ = compute_party_alignment(votes_pl, [], [], bench_votes=bench)
        self.assertEqual(details_pl[0]["orientacao"], "NAO")
        self.assertEqual(details_pl[0]["orientacao_fonte"], "MAIORIA_PL")
        self.assertEqual(details_pl[0]["status"], "aligned")
        self.assertEqual(_orientation_parties({"codTipoLideranca": "P", "siglaPartidoBloco": "PT"}), {"PT"})
        self.assertEqual(_orientation_parties({"codTipoLideranca": "F", "siglaPartidoBloco": "Fdr PT-PCdoB-PV"}, voting_date="2022-06-01"), {"PT", "PCDOB", "PV"})
        self.assertEqual(_orientation_parties({"codTipoLideranca": "F", "siglaPartidoBloco": "Fdr PT-PCdoB-PV"}, voting_date="2021-01-01"), set())

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
