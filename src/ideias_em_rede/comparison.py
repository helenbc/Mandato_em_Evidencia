"""Comparação exploratória entre posições em falas e votos nominais por tema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .alignment import canonical_vote, read_jsonl
from .deputies import normalize_text
from .io_utils import read_json, utc_now_iso, write_json, write_jsonl


def compare_speeches_and_votes(
    positions: list[dict[str, Any]],
    votes: list[dict[str, Any]],
    votings: list[dict[str, Any]],
    comparison_config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Cruza fala e voto quando deputado, votação e vocabulário temático coincidem.

    O mapeamento político de ``Sim`` e ``Não`` é explicitado no arquivo de
    configuração; não é inferido automaticamente da descrição da votação.
    """

    votes_by_key = {}
    for vote in votes:
        deputy = vote.get("deputado_") or vote.get("deputado") or {}
        if deputy.get("id") is not None:
            votes_by_key[(str(vote["votacao_id"]), int(deputy["id"]))] = vote
    votings_by_id = {str(voting["id"]): voting for voting in votings}
    comparisons = []
    for specification in comparison_config.get("votings", []):
        voting_id = str(specification["votacao_id"])
        normalized_terms = [normalize_text(term) for term in specification["topic_terms"]]
        for position in positions:
            if position.get("extraction_status") != "ok":
                continue
            position_text = normalize_text(
                " ".join(
                    str(position.get(field) or "")
                    for field in ("subject", "topic", "question", "opinion")
                )
            )
            if not any(term in position_text for term in normalized_terms):
                continue
            deputy_id = int(position["deputado_id"])
            vote = votes_by_key.get((voting_id, deputy_id))
            if not vote:
                continue
            canonical = canonical_vote(vote.get("tipoVoto"))
            if canonical == "SIM":
                vote_stance = specification["yes_stance"]
            elif canonical == "NAO":
                vote_stance = specification["no_stance"]
            else:
                vote_stance = "NAO_DETERMINADO"
            speech_stance = position.get("stance")
            if "NAO_DETERMINADO" in {speech_stance, vote_stance} or speech_stance == "MISTO":
                result = "INCONCLUSIVO"
            elif speech_stance == vote_stance:
                result = "COERENTE"
            else:
                result = "DIVERGENTE"
            voting = votings_by_id.get(voting_id, {})
            comparisons.append(
                {
                    "comparison_id": f"{position['candidate_id']}:{voting_id}",
                    "deputado_id": deputy_id,
                    "deputado_nome": position["deputado_nome"],
                    "partido": position.get("partido"),
                    "tema": position.get("topic"),
                    "questao_fala": position.get("question"),
                    "posicao_fala": speech_stance,
                    "evidencia_fala": position.get("evidence_quote"),
                    "confianca_fala": position.get("confidence"),
                    "votacao_id": voting_id,
                    "questao_voto": specification["question"],
                    "voto": vote.get("tipoVoto"),
                    "posicao_voto": vote_stance,
                    "descricao_votacao": voting.get("descricao"),
                    "votacao_uri": voting.get("uri"),
                    "resultado": result,
                }
            )
    counts = {status: 0 for status in ("COERENTE", "DIVERGENTE", "INCONCLUSIVO")}
    for comparison in comparisons:
        counts[comparison["resultado"]] += 1
    return comparisons, {
        "generated_at": utc_now_iso(),
        "sample_description": comparison_config.get("description"),
        "total": len(comparisons),
        "counts": counts,
        "warning": "Comparacao exploratoria; nao representa um score geral do parlamentar.",
    }


def run_comparison(
    positions_path: Path,
    votes_path: Path,
    votings_path: Path,
    config_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Executa a comparação configurada e grava detalhes e contagens."""

    comparisons, summary = compare_speeches_and_votes(
        read_jsonl(positions_path),
        read_jsonl(votes_path),
        read_jsonl(votings_path),
        read_json(config_path),
    )
    write_jsonl(output_dir / "fala_voto_detalhes.jsonl", comparisons)
    write_json(output_dir / "fala_voto_resumo.json", summary)
    return summary
