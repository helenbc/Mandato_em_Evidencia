"""Gold set humano — schema, validação e métrica de avaliação.

Schema JSONL (uma linha por anotação):
{
  "candidate_id": "phbr:7:42:1",          // obrigatório, identifica a fala candidata
  "stance": "FAVORAVEL",                  // obrigatório, enum STANCES
  "evidence_quote": "citação literal...", // obrigatório, não vazio
  "anotador": "nome",                     // opcional
  "observacao": "...",                     // opcional
  ... outros campos livres ...
}

A curadoria real ainda está pendente (config/gold_set.jsonl não existe por padrão).
Use config/gold_set.example.jsonl como modelo com 2 linhas de exemplo
fictícias marcadas com anotador "exemplo".

Métrica evaluate_gold:
- casa por candidate_id entre positions (saída de run_position_extraction)
  e gold_rows
- só conta matches com extraction_status == "ok"
- invalid_evidence conta extraction_status != "ok"
- accuracy = correct / matches (0.0 se matches==0)
- by_stance detalha por stance esperado do gold
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

STANCES: frozenset[str] = frozenset(
    {"FAVORAVEL", "CONTRARIO", "MISTO", "NAO_DETERMINADO"}
)


def validate_gold_row(row: dict[str, Any]) -> dict[str, Any]:
    """Valida uma linha do gold set. Levanta ValueError com mensagem clara se inválida."""

    if not isinstance(row, dict):
        raise ValueError("gold row deve ser um objeto JSON (dict)")

    cid = row.get("candidate_id")
    if not isinstance(cid, str) or not cid.strip():
        raise ValueError("candidate_id ausente ou vazio")

    stance = row.get("stance")
    if stance not in STANCES:
        raise ValueError(f"stance fora do enum: {stance!r}. Esperado um de {sorted(STANCES)}")

    ev = row.get("evidence_quote")
    if not isinstance(ev, str) or not ev.strip():
        raise ValueError("evidence_quote vazia ou ausente")

    return row


def evaluate_gold(
    positions: list[dict[str, Any]], gold_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compara stances da LLM vs gold, casando por candidate_id.

    Só conta matches com extraction_status == "ok". Linhas com status != "ok"
    contam como invalid_evidence. Retorna dict com total, matches, accuracy,
    invalid_evidence e by_stance.
    """

    # valida gold previamente (opcional mas garante schema)
    for r in gold_rows:
        validate_gold_row(r)

    pos_by_id: dict[str, dict[str, Any]] = {}
    for p in positions:
        cid = p.get("candidate_id")
        if isinstance(cid, str) and cid.strip():
            pos_by_id[cid] = p

    total = len(gold_rows)
    matches = 0
    invalid_evidence = 0
    correct = 0

    by_stance: dict[str, dict[str, Any]] = {}

    for gold in gold_rows:
        expected = gold["stance"]
        entry = by_stance.setdefault(
            expected,
            {"total": 0, "matches": 0, "correct": 0, "invalid_evidence": 0},
        )
        entry["total"] += 1

        cid = gold["candidate_id"]
        pos = pos_by_id.get(cid)
        if pos is None:
            continue
        status = pos.get("extraction_status")
        if status != "ok":
            invalid_evidence += 1
            entry["invalid_evidence"] += 1
            continue
        matches += 1
        entry["matches"] += 1
        llm_stance = pos.get("stance")
        if llm_stance == expected:
            correct += 1
            entry["correct"] += 1

    accuracy: float = (correct / matches) if matches else 0.0

    # calcula accuracy por stance
    for stance, data in by_stance.items():
        m = data["matches"]
        c = data["correct"]
        data["accuracy"] = (c / m) if m else 0.0

    return {
        "total": total,
        "matches": matches,
        "correct": correct,
        "accuracy": accuracy,
        "invalid_evidence": invalid_evidence,
        "by_stance": by_stance,
    }
