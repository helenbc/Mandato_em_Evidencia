"""Cálculo conservador de alinhamento entre voto nominal e orientação partidária."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from .deputies import normalize_text
from .io_utils import utc_now_iso, write_json, write_jsonl


FEDERATION_MEMBERS = {
    "FDR PT PCDOB PV": {"PT", "PCDOB", "PV"},
    "FDR PSOL REDE": {"PSOL", "REDE"},
}

COMPARABLE_VOTES = {"SIM", "NAO", "ABSTENCAO", "OBSTRUCAO"}
MINIMUM_BENCH_VOTES = 2


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Carrega um JSONL completo em memória para as etapas analíticas."""

    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def canonical_vote(value: Any) -> str | None:
    """Converte grafias da Câmara em um conjunto pequeno de valores canônicos."""

    normalized = normalize_text(str(value or ""))
    aliases = {
        "SIM": "SIM",
        "NAO": "NAO",
        "ABSTENCAO": "ABSTENCAO",
        "OBSTRUCAO": "OBSTRUCAO",
        "LIBERADO": "LIBERADO",
        "ARTIGO 17": "ARTIGO_17",
    }
    return aliases.get(normalized)


def _parse_iso_date(value: Any) -> date | None:
    """Converte YYYY-MM-DD ou ISO datetime em date; None se ausente/inválido."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    for sep in ("T", " "):
        if sep in text:
            text = text.split(sep)[0]
            break
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _extract_voting_date(voting: dict[str, Any]) -> date | None:
    """Extrai a data da votação (campo data ou dataHoraRegistro)."""

    for key in ("data", "dataHoraRegistro", "dataHoraVotacao", "dataVotacao"):
        raw = voting.get(key)
        if raw:
            parsed = _parse_iso_date(raw)
            if parsed is not None:
                return parsed
    return None


def _federation_map_for_date(voting_date: date | str | None) -> dict[str, set[str]]:
    """Carrega federações vigentes numa data (inicio <= data <= fim).

    Lê config/federacoes.json em formato versionado; se ausente ou inválido,
    retorna o dicionário estático FEDERATION_MEMBERS para não quebrar testes.
    Se voting_date is None, retorna todas as federações (compatibilidade).
    """

    target: date | None = None
    if voting_date is not None:
        target = _parse_iso_date(voting_date)

    config_path = Path(__file__).resolve().parents[2] / "config" / "federacoes.json"
    if config_path.is_file():
        try:
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            result: dict[str, set[str]] = {}
            for entry in raw:
                sigla = entry.get("sigla")
                if not sigla:
                    continue
                sigla_norm = normalize_text(str(sigla))
                inicio = _parse_iso_date(entry.get("inicio"))
                fim = _parse_iso_date(entry.get("fim"))
                if target is not None:
                    if inicio is not None and target < inicio:
                        continue
                    if fim is not None and target > fim:
                        continue
                membros = entry.get("membros") or []
                membros_norm = {normalize_text(str(m)) for m in membros if normalize_text(str(m))}
                if sigla_norm:
                    result[sigla_norm] = membros_norm
            return result
        except Exception:
            return FEDERATION_MEMBERS
    return FEDERATION_MEMBERS


def _orientation_parties(
    orientation: dict[str, Any], voting_date: date | str | None = None
) -> set[str]:
    label = normalize_text(orientation.get("siglaPartidoBloco"))
    if orientation.get("codTipoLideranca") == "P":
        return {label} if label else set()
    fed_map = _federation_map_for_date(voting_date)
    return fed_map.get(label, set())


def resolve_orientation(
    party: str,
    orientations: Iterable[dict[str, Any]],
    voting_date: date | str | None = None,
) -> tuple[str, str | None, str | None]:
    """Resolve a orientação aplicável ao partido sem inferir blocos truncados.

    Retorna ``(status, orientação, fonte)``. Apenas uma orientação direta do
    partido ou de federação com composição declarada é considerada segura.
    Se voting_date for informado, apenas federações vigentes naquela data
    são consideradas.
    """

    expected_party = normalize_text(party)
    candidates: list[tuple[str, str]] = []
    for orientation in orientations:
        if expected_party not in _orientation_parties(orientation, voting_date):
            continue
        value = canonical_vote(orientation.get("orientacaoVoto"))
        if value:
            candidates.append((value, str(orientation.get("siglaPartidoBloco") or "")))
    if not candidates:
        return "no_orientation", None, None
    unique_values = {value for value, _ in candidates}
    if len(unique_values) > 1:
        return "ambiguous_orientation", None, ", ".join(label for _, label in candidates)
    value, label = candidates[0]
    if value == "LIBERADO":
        return "released", value, label
    return "found", value, label


def _bench_index(
    bench_votes: list[dict[str, Any]],
) -> dict[tuple[str, str], list[tuple[int | None, str]]]:
    """Indexa o placar completo por (votação, partido) para o fallback."""

    index: dict[tuple[str, str], list[tuple[int | None, str]]] = defaultdict(list)
    for vote in bench_votes:
        deputy = vote.get("deputado_") or vote.get("deputado") or {}
        try:
            deputy_id: int | None = int(deputy.get("id"))
        except (TypeError, ValueError):
            deputy_id = None
        party = normalize_text(str(deputy.get("siglaPartido") or ""))
        value = canonical_vote(vote.get("tipoVoto"))
        if not party or value not in COMPARABLE_VOTES:
            continue
        index[(str(vote.get("votacao_id")), party)].append((deputy_id, value))
    return index


def party_majority(
    party: str,
    voting_id: str,
    bench_index: dict[tuple[str, str], list[tuple[int | None, str]]],
    exclude_deputy_id: int | None,
) -> tuple[str | None, int]:
    """Calcula a maioria da bancada numa votação como fallback.

    Considera somente votos canônicos comparáveis do mesmo partido (sigla da
    época, registrada no próprio voto), excluindo o parlamentar avaliado
    (leave-one-out). Exige ao menos ``MINIMUM_BENCH_VOTES`` votos de colegas;
    empate no topo significa sem maioria. Retorna ``(valor, base)``.
    """

    rows = [
        (deputy_id, value)
        for deputy_id, value in bench_index.get(
            (voting_id, normalize_text(party)), []
        )
        if deputy_id != exclude_deputy_id
    ]
    base = len(rows)
    if base < MINIMUM_BENCH_VOTES:
        return None, base
    counts: dict[str, int] = {}
    for _, value in rows:
        counts[value] = counts.get(value, 0) + 1
    top = max(counts.values())
    winners = [value for value, total in counts.items() if total == top]
    if len(winners) != 1:
        return None, base
    return winners[0], base


def compute_party_alignment(
    votes: list[dict[str, Any]],
    orientations: list[dict[str, Any]],
    votings: list[dict[str, Any]],
    bench_votes: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Calcula detalhes por voto e o resumo agregado por parlamentar.

    Fórmula: ``alinhados / (alinhados + divergentes)``. Votos sem orientação
    comparável continuam nos detalhes e na cobertura, mas não no denominador.

    Quando ``bench_votes`` (placar completo) é informado, votos com status
    ``no_orientation`` usam a maioria da bancada como fallback
    (``orientacao_fonte`` vira ``MAIORIA_<PARTIDO>``). A orientação oficial
    sempre prevalece em caso de conflito.
    """

    orientations_by_voting: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for orientation in orientations:
        orientations_by_voting[str(orientation["votacao_id"])].append(orientation)
    votings_by_id = {str(voting["id"]): voting for voting in votings}
    bench_index = _bench_index(bench_votes) if bench_votes else None
    details: list[dict[str, Any]] = []
    majority_counts: defaultdict[int, int] = defaultdict(int)

    for vote in votes:
        voting_id = str(vote["votacao_id"])
        deputy = vote.get("deputado_") or vote.get("deputado") or {}
        party = str(deputy.get("siglaPartido") or "")
        vote_value = canonical_vote(vote.get("tipoVoto"))
        voting = votings_by_id.get(voting_id, {})
        voting_date = _extract_voting_date(voting)
        orientation_status, orientation_value, orientation_source = resolve_orientation(
            party, orientations_by_voting[voting_id], voting_date
        )
        majority_used = False
        if vote_value not in COMPARABLE_VOTES:
            status = "excluded_vote"
        elif orientation_status != "found":
            status = orientation_status
            if orientation_status == "no_orientation" and bench_index is not None:
                try:
                    deputy_id = int(deputy.get("id"))
                except (TypeError, ValueError):
                    deputy_id = None
                majority_value, _base = party_majority(
                    party, voting_id, bench_index, deputy_id
                )
                if majority_value is not None:
                    orientation_value = majority_value
                    orientation_source = f"MAIORIA_{party}" if party else "MAIORIA"
                    status = "aligned" if vote_value == majority_value else "diverged"
                    majority_used = True
                    if deputy_id is not None:
                        majority_counts[deputy_id] += 1
        elif orientation_value not in COMPARABLE_VOTES:
            status = "excluded_orientation"
        else:
            status = "aligned" if vote_value == orientation_value else "diverged"
        details.append(
            {
                "votacao_id": voting_id,
                "data": voting.get("data") or voting.get("dataHoraRegistro"),
                "descricao": voting.get("descricao"),
                "votacao_uri": voting.get("uri"),
                "deputado_id": deputy.get("id"),
                "deputado_nome": deputy.get("nome"),
                "partido": party,
                "uf": deputy.get("siglaUf"),
                "voto_original": vote.get("tipoVoto"),
                "voto": vote_value,
                "orientacao": orientation_value,
                "orientacao_fonte": orientation_source,
                "status": status,
            }
        )

    details.sort(key=lambda row: (str(row["deputado_nome"]), str(row["votacao_id"])))
    grouped: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for detail in details:
        if detail["deputado_id"] is not None:
            grouped[int(detail["deputado_id"])].append(detail)

    deputies = []
    for deputy_id, rows in grouped.items():
        status_counts: defaultdict[str, int] = defaultdict(int)
        for row in rows:
            status_counts[row["status"]] += 1
        comparable = status_counts["aligned"] + status_counts["diverged"]
        deputies.append(
            {
                "deputado_id": deputy_id,
                "deputado_nome": rows[0]["deputado_nome"],
                "partido": rows[0]["partido"],
                "uf": rows[0]["uf"],
                "recorded_votes": len(rows),
                "comparable_votes": comparable,
                "aligned_votes": status_counts["aligned"],
                "diverged_votes": status_counts["diverged"],
                "majority_fallback_votes": majority_counts.get(deputy_id, 0),
                "released": status_counts["released"],
                "no_orientation": status_counts["no_orientation"],
                "ambiguous_orientation": status_counts["ambiguous_orientation"],
                "excluded_votes": status_counts["excluded_vote"]
                + status_counts["excluded_orientation"],
                "alignment_score": (
                    round(status_counts["aligned"] / comparable, 4) if comparable else None
                ),
                "coverage": round(comparable / len(rows), 4) if rows else 0.0,
            }
        )
    deputies.sort(
        key=lambda row: (
            row["alignment_score"] is None,
            -(row["alignment_score"] or 0),
            str(row["deputado_nome"]),
        )
    )
    total_comparable = sum(row["comparable_votes"] for row in deputies)
    total_aligned = sum(row["aligned_votes"] for row in deputies)
    summary = {
        "generated_at": utc_now_iso(),
        "methodology": {
            "denominator": "Votos com orientacao explicita do partido ou federacao identificavel, ou maioria da bancada como fallback.",
            "fallback": "Sem orientacao explicita, usa a maioria da bancada na votacao (quorum minimo de 2 colegas, leave-one-out, empate = sem base; fonte MAIORIA_<PARTIDO>). A orientacao oficial prevalece em conflito.",
            "excluded": [
                "bancada liberada",
                "orientacao ausente ou ambigua",
                "Artigo 17 e valores nao reconhecidos",
                "ausencias, que nao aparecem no arquivo de votos",
            ],
        },
        "totals": {
            "recorded_votes": len(details),
            "comparable_votes": total_comparable,
            "aligned_votes": total_aligned,
            "diverged_votes": sum(row["diverged_votes"] for row in deputies),
            "majority_fallback_votes": sum(row["majority_fallback_votes"] for row in deputies),
            "alignment_score": (
                round(total_aligned / total_comparable, 4) if total_comparable else None
            ),
        },
        "deputies": deputies,
    }
    return details, summary


def run_party_alignment(
    votes_path: Path,
    orientations_path: Path,
    votings_path: Path,
    output_dir: Path,
    bench_votes_path: Path | None = None,
) -> dict[str, Any]:
    """Lê insumos JSONL, calcula a métrica e grava detalhe e resumo.

    O placar completo (``votos_completos.jsonl``) é opcional: quando ausente,
    o cálculo usa somente a orientação oficial, como antes.
    """

    if bench_votes_path is None:
        candidate = Path(votes_path).parent / "votos_completos.jsonl"
        bench_votes_path = candidate if candidate.is_file() else None
    bench_votes = read_jsonl(bench_votes_path) if bench_votes_path is not None else None
    details, summary = compute_party_alignment(
        read_jsonl(votes_path),
        read_jsonl(orientations_path),
        read_jsonl(votings_path),
        bench_votes=bench_votes,
    )
    write_jsonl(output_dir / "alinhamento_detalhes.jsonl", details)
    write_json(output_dir / "alinhamento_resumo.json", summary)
    return summary
