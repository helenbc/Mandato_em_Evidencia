"""Consolidação dos resultados do pipeline no documento consumido pelo site."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .alignment import read_jsonl
from .io_utils import read_json, utc_now_iso, write_json


def _optional_json(path: Path, default: Any) -> Any:
    return read_json(path) if path.is_file() else default


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path) if path.is_file() else []


def export_dashboard_data(
    processed_dir: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Monta uma visão por deputado e grava o JSON incorporado ao frontend.

    Arquivos opcionais permitem abrir o site antes da chamada à LLM. Nesse caso,
    as falas aparecem como pendentes e nenhuma classificação é simulada.
    """

    resolution = _optional_json(processed_dir / "deputados_resolvidos.json", {"deputies": []})
    alignment = _optional_json(processed_dir / "analysis/alinhamento_resumo.json", {"deputies": [], "totals": {}})
    alignment_details = _optional_jsonl(processed_dir / "analysis/alinhamento_detalhes.jsonl")
    candidates = _optional_jsonl(processed_dir / "analysis/posicoes_candidatas.jsonl")
    positions = _optional_jsonl(processed_dir / "analysis/posicoes_llm.jsonl")
    comparisons = _optional_jsonl(processed_dir / "analysis/fala_voto_detalhes.jsonl")
    comparison_summary = _optional_json(processed_dir / "analysis/fala_voto_resumo.json", {"total": 0, "counts": {}})
    collection = _optional_json(processed_dir / "camara/summary.json", {})

    alignment_by_deputy = {int(row["deputado_id"]): row for row in alignment.get("deputies", [])}
    details_by_deputy: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in alignment_details:
        details_by_deputy[int(row["deputado_id"])].append(row)
    positions_by_deputy: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in positions:
        positions_by_deputy[int(row["deputado_id"])].append(row)
    candidates_by_deputy: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        candidates_by_deputy[int(row["deputado_id"])].append(row)
    comparisons_by_deputy: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in comparisons:
        comparisons_by_deputy[int(row["deputado_id"])].append(row)

    deputies = []
    for source in resolution.get("deputies", []):
        if source.get("resolution_status") != "matched":
            continue
        camara = source["camara"]
        deputy_id = int(camara["id"])
        position_rows = positions_by_deputy[deputy_id]
        if position_rows:
            speech_rows = [
                {
                    "status": row.get("extraction_status"),
                    "subject": row.get("subject"),
                    "topic": row.get("topic"),
                    "question": row.get("question"),
                    "stance": row.get("stance"),
                    "evidence": row.get("evidence_quote"),
                    "confidence": row.get("confidence"),
                    "hearing_id": row.get("hearing_id"),
                    "model": row.get("model"),
                }
                for row in position_rows[:5]
            ]
        else:
            speech_rows = [
                {
                    "status": "pending_llm",
                    "subject": row.get("subject"),
                    "topic": None,
                    "question": row.get("opinion"),
                    "stance": "NAO_CLASSIFICADO",
                    "evidence": row.get("opinion"),
                    "confidence": None,
                    "hearing_id": row.get("hearing_id"),
                    "model": None,
                }
                for row in candidates_by_deputy[deputy_id][:3]
            ]
        deputies.append(
            {
                "id": deputy_id,
                "name": camara.get("nome"),
                "party": camara.get("siglaPartido"),
                "uf": camara.get("siglaUf"),
                "photo": camara.get("urlFoto"),
                "hearingCount": source.get("hearing_count"),
                "opinionCount": source.get("opinion_count"),
                "alignment": alignment_by_deputy.get(deputy_id),
                "alignmentDetails": details_by_deputy[deputy_id],
                "speeches": speech_rows,
                "comparisons": comparisons_by_deputy[deputy_id],
            }
        )
    deputies.sort(key=lambda row: str(row["name"]))
    dashboard = {
        "generatedAt": utc_now_iso(),
        "project": {
            "name": "Mandato em Evidencia",
            "description": "Falas, votos e alinhamento partidario com fontes rastreaveis.",
            "disclaimer": "Painel exploratorio de transparencia. Nao recomenda candidatos nem produz ranking geral.",
        },
        "stats": {
            "deputies": len(deputies),
            "hearings": 206,
            "recordedVotes": alignment.get("totals", {}).get("recorded_votes", 0),
            "comparableVotes": alignment.get("totals", {}).get("comparable_votes", 0),
            "classifiedSpeeches": len(positions),
            "comparisons": len(comparisons),
        },
        "collection": collection,
        "alignmentMethodology": alignment.get("methodology", {}),
        "comparisonSummary": comparison_summary,
        "llmStatus": "ready" if positions else "awaiting_api_key",
        "deputies": deputies,
    }
    write_json(output_path, dashboard)
    return dashboard
