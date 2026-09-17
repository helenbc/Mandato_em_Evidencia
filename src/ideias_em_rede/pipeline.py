"""Coleta concorrente de votações, votos nominais e orientações partidárias."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .camara import CamaraClient
from .io_utils import utc_now_iso, write_json, write_jsonl


def _validate_date(value: str) -> str:
    date.fromisoformat(value)
    return value


def split_range(start_date: str, end_date: str, batch_days: int) -> list[tuple[str, str]]:
    """Fatia intervalo inclusivo em janelas de batch_days dias.

    Retorna lista de tuplas (start, end) em formato YYYY-MM-DD.
    """

    start = date.fromisoformat(_validate_date(start_date))
    end = date.fromisoformat(_validate_date(end_date))
    if start > end:
        raise ValueError("start_date nao pode ser posterior a end_date")
    if not isinstance(batch_days, int) or batch_days <= 0:
        raise ValueError("batch_days deve ser inteiro positivo")
    result: list[tuple[str, str]] = []
    current = start
    delta = timedelta(days=batch_days - 1)
    one_day = timedelta(days=1)
    while current <= end:
        batch_end = min(current + delta, end)
        result.append((current.isoformat(), batch_end.isoformat()))
        current = batch_end + one_day
    return result


def _deputy_id_from_vote(vote: dict[str, Any]) -> int | None:
    deputy = vote.get("deputado_") or vote.get("deputado") or {}
    value = deputy.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def matched_deputy_ids(resolution: dict[str, Any]) -> set[int]:
    """Retorna somente IDs cuja resolução foi considerada segura."""

    result: set[int] = set()
    for deputy in resolution.get("deputies", []):
        if deputy.get("resolution_status") != "matched":
            continue
        value = (deputy.get("camara") or {}).get("id")
        if value is not None:
            result.add(int(value))
    return result


def collect_votes_and_orientations(
    resolution: dict[str, Any],
    client: CamaraClient,
    start_date: str,
    end_date: str,
    output_dir: Path,
    max_votings: int | None = None,
    organ: str | None = None,
    workers: int = 4,
    batch_days: int | None = None,
) -> dict[str, Any]:
    """Coleta votações do período e conserva votos dos deputados selecionados.

    As votações são consultadas em paralelo. Orientações só são baixadas quando
    ao menos um deputado selecionado possui voto naquela votação. Para essas
    votações, o placar completo também é conservado em ``votos_completos.jsonl``
    para permitir o cálculo da maioria da bancada como fallback.
    """

    start_date = _validate_date(start_date)
    end_date = _validate_date(end_date)
    if start_date > end_date:
        raise ValueError("start_date nao pode ser posterior a end_date")
    if batch_days is not None and (not isinstance(batch_days, int) or batch_days <= 0):
        raise ValueError("batch_days deve ser inteiro positivo")
    selected_ids = matched_deputy_ids(resolution)
    if not selected_ids:
        raise ValueError("Nenhum deputado com resolution_status=matched")

    batches: list[tuple[str, str]] | None = None
    if batch_days is not None:
        batches = split_range(start_date, end_date, batch_days)

    votings: list[dict[str, Any]] = []
    if batches is not None:
        votings_by_id: dict[str, dict[str, Any]] = {}
        for b_start, b_end in batches:
            for voting in client.list_votings(b_start, b_end):
                if organ and str(voting.get("siglaOrgao", "")).upper() != organ.upper():
                    continue
                vid = str(voting["id"])
                if vid not in votings_by_id:
                    votings_by_id[vid] = voting
                if max_votings is not None and len(votings_by_id) >= max_votings:
                    break
            if max_votings is not None and len(votings_by_id) >= max_votings:
                break
        votings = list(votings_by_id.values())
    else:
        for voting in client.list_votings(start_date, end_date):
            if organ and str(voting.get("siglaOrgao", "")).upper() != organ.upper():
                continue
            votings.append(voting)
            if max_votings is not None and len(votings) >= max_votings:
                break

    matched_votings: list[dict[str, Any]] = []
    selected_votes: list[dict[str, Any]] = []
    bench_votes: list[dict[str, Any]] = []
    orientations: list[dict[str, Any]] = []

    def fetch(
        voting: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        votes = client.voting_votes(str(voting["id"]))
        filtered = [vote for vote in votes if _deputy_id_from_vote(vote) in selected_ids]
        return voting, filtered, votes

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch, voting): voting for voting in votings}
        for future in as_completed(futures):
            voting, votes, all_votes = future.result()
            if not votes:
                continue
            voting_id = str(voting["id"])
            matched_votings.append({**voting, "selected_vote_count": len(votes)})
            selected_votes.extend({"votacao_id": voting_id, **vote} for vote in votes)
            bench_votes.extend({"votacao_id": voting_id, **vote} for vote in all_votes)
            for orientation in client.voting_orientations(voting_id):
                orientations.append({"votacao_id": voting_id, **orientation})

    # Deduplicação por id para modo batch e idempotência
    matched_votings_by_id: dict[str, dict[str, Any]] = {}
    for row in matched_votings:
        matched_votings_by_id[str(row["id"])] = row
    matched_votings = list(matched_votings_by_id.values())

    selected_by_key: dict[tuple[str, int | None], dict[str, Any]] = {}
    for vote in selected_votes:
        key = (str(vote.get("votacao_id")), _deputy_id_from_vote(vote))
        if key not in selected_by_key:
            selected_by_key[key] = vote
    selected_votes = list(selected_by_key.values())

    bench_by_key: dict[tuple[str, int | None], dict[str, Any]] = {}
    for vote in bench_votes:
        key = (str(vote.get("votacao_id")), _deputy_id_from_vote(vote))
        if key not in bench_by_key:
            bench_by_key[key] = vote
    bench_votes = list(bench_by_key.values())

    orientations_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for ori in orientations:
        key = (str(ori.get("votacao_id")), str(ori.get("siglaBancada") or ""))
        if key not in orientations_by_key:
            orientations_by_key[key] = ori
    orientations = list(orientations_by_key.values())

    matched_votings.sort(key=lambda row: (row.get("dataHoraRegistro") or "", str(row["id"])))
    selected_votes.sort(key=lambda row: (str(row["votacao_id"]), _deputy_id_from_vote(row) or 0))
    bench_votes.sort(key=lambda row: (str(row["votacao_id"]), _deputy_id_from_vote(row) or 0))
    orientations.sort(
        key=lambda row: (str(row["votacao_id"]), str(row.get("siglaBancada") or ""))
    )

    write_jsonl(output_dir / "votacoes.jsonl", matched_votings)
    write_jsonl(output_dir / "votos.jsonl", selected_votes)
    write_jsonl(output_dir / "votos_completos.jsonl", bench_votes)
    write_jsonl(output_dir / "orientacoes.jsonl", orientations)
    summary: dict[str, Any] = {
        "generated_at": utc_now_iso(),
        "period": {"start": start_date, "end": end_date},
        "organ_filter": organ,
        "selected_deputy_ids": sorted(selected_ids),
        "listed_votings": len(votings),
        "votings_with_selected_votes": len(matched_votings),
        "selected_votes": len(selected_votes),
        "bench_votes": len(bench_votes),
        "orientations": len(orientations),
        "output_files": {
            "votacoes": str(output_dir / "votacoes.jsonl"),
            "votos": str(output_dir / "votos.jsonl"),
            "votos_completos": str(output_dir / "votos_completos.jsonl"),
            "orientacoes": str(output_dir / "orientacoes.jsonl"),
        },
    }
    if batches is not None:
        summary["batch_days"] = batch_days
        summary["batches"] = [[s, e] for s, e in batches]
    write_json(output_dir / "summary.json", summary)
    return summary
