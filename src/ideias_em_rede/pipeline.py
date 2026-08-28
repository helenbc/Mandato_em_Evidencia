"""Coleta concorrente de votações, votos nominais e orientações partidárias."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any

from .camara import CamaraClient
from .io_utils import utc_now_iso, write_json, write_jsonl


def _validate_date(value: str) -> str:
    date.fromisoformat(value)
    return value


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
) -> dict[str, Any]:
    """Coleta votações do período e conserva votos dos deputados selecionados.

    As votações são consultadas em paralelo. Orientações só são baixadas quando
    ao menos um deputado selecionado possui voto naquela votação.
    """

    start_date = _validate_date(start_date)
    end_date = _validate_date(end_date)
    if start_date > end_date:
        raise ValueError("start_date nao pode ser posterior a end_date")
    selected_ids = matched_deputy_ids(resolution)
    if not selected_ids:
        raise ValueError("Nenhum deputado com resolution_status=matched")

    votings: list[dict[str, Any]] = []
    for voting in client.list_votings(start_date, end_date):
        if organ and str(voting.get("siglaOrgao", "")).upper() != organ.upper():
            continue
        votings.append(voting)
        if max_votings is not None and len(votings) >= max_votings:
            break

    matched_votings: list[dict[str, Any]] = []
    selected_votes: list[dict[str, Any]] = []
    orientations: list[dict[str, Any]] = []

    def fetch(voting: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        votes = client.voting_votes(str(voting["id"]))
        filtered = [vote for vote in votes if _deputy_id_from_vote(vote) in selected_ids]
        return voting, filtered

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(fetch, voting): voting for voting in votings}
        for future in as_completed(futures):
            voting, votes = future.result()
            if not votes:
                continue
            voting_id = str(voting["id"])
            matched_votings.append({**voting, "selected_vote_count": len(votes)})
            selected_votes.extend({"votacao_id": voting_id, **vote} for vote in votes)
            for orientation in client.voting_orientations(voting_id):
                orientations.append({"votacao_id": voting_id, **orientation})

    matched_votings.sort(key=lambda row: (row.get("dataHoraRegistro") or "", str(row["id"])))
    selected_votes.sort(key=lambda row: (str(row["votacao_id"]), _deputy_id_from_vote(row) or 0))
    orientations.sort(
        key=lambda row: (str(row["votacao_id"]), str(row.get("siglaBancada") or ""))
    )

    write_jsonl(output_dir / "votacoes.jsonl", matched_votings)
    write_jsonl(output_dir / "votos.jsonl", selected_votes)
    write_jsonl(output_dir / "orientacoes.jsonl", orientations)
    summary = {
        "generated_at": utc_now_iso(),
        "period": {"start": start_date, "end": end_date},
        "organ_filter": organ,
        "selected_deputy_ids": sorted(selected_ids),
        "listed_votings": len(votings),
        "votings_with_selected_votes": len(matched_votings),
        "selected_votes": len(selected_votes),
        "orientations": len(orientations),
        "output_files": {
            "votacoes": str(output_dir / "votacoes.jsonl"),
            "votos": str(output_dir / "votos.jsonl"),
            "orientacoes": str(output_dir / "orientacoes.jsonl"),
        },
    }
    write_json(output_dir / "summary.json", summary)
    return summary
