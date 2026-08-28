"""Extração de parlamentares do dataset e resolução na base oficial da Câmara."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Iterable, Protocol

from .dataset import DatasetPaths, iter_lds, iter_nli
from .io_utils import utc_now_iso


DEPUTY_PATTERN = re.compile(r"\bdeputad[oa]\b", re.IGNORECASE)
PARTY_UF_PATTERN = re.compile(
    r"(?P<party>[A-Za-zÀ-ÿ0-9./+ _-]+?)\s*-\s*(?P<uf>[A-Z]{2})\s*\)?\s*$"
)


class DeputySearchClient(Protocol):
    """Contrato mínimo usado para permitir clientes falsos nos testes."""

    def search_deputies(
        self, name: str, legislature: int | None = None
    ) -> list[dict[str, Any]]: ...


def normalize_text(value: str | None) -> str:
    """Normaliza nomes e siglas removendo acentos, pontuação e espaços duplicados."""

    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", ascii_value).upper().split())


def parse_deputy_cargo(cargo: str | None) -> dict[str, str | None] | None:
    """Extrai partido e UF de cargos textuais que identificam deputado ou deputada."""

    if not cargo or not DEPUTY_PATTERN.search(cargo):
        return None
    party: str | None = None
    uf: str | None = None
    match = PARTY_UF_PATTERN.search(cargo)
    if match:
        uf = match.group("uf").upper()
        party_text = match.group("party").strip(" ()")
        if "/" in party_text:
            party_text = party_text.rsplit("/", 1)[-1]
        party_text = re.sub(r"^(BLOCO|FEDERACAO|FEDERAÇÃO)\s+", "", party_text, flags=re.I)
        party = party_text.strip() or None
    return {"party": party, "uf": uf}


def _iter_people(
    paths: DatasetPaths, source: str
) -> Iterable[tuple[int, dict[str, Any], str]]:
    if source in {"lds", "both"}:
        for record in iter_lds(paths):
            for person in record["metadados"]["envolvidos"]:
                yield record["id"], person, "lds"
    if source in {"nli", "both"}:
        for record in iter_nli(paths):
            for person in record["metadados_extraidos"]["envolvidos"]:
                yield record["id"], person, "nli"


def extract_deputies(
    paths: DatasetPaths, source: str = "lds", limit: int | None = None
) -> dict[str, Any]:
    """Agrupa deputados citados e contabiliza audiências e opiniões associadas."""

    if source not in {"lds", "nli", "both"}:
        raise ValueError("source deve ser lds, nli ou both")
    paths.require_files()
    grouped: dict[str, dict[str, Any]] = {}
    seen: set[tuple[int, str, str, str]] = set()

    for hearing_id, person, origin in _iter_people(paths, source):
        name = str(person.get("nome") or "").strip()
        cargo = str(person.get("cargo") or "").strip()
        parsed = parse_deputy_cargo(cargo)
        if not name or parsed is None:
            continue
        key = normalize_text(name)
        opinions = person.get("opinioes", [])
        if not isinstance(opinions, list):
            opinions = []
        deduplication_key = (hearing_id, key, cargo, origin)
        if deduplication_key in seen:
            continue
        seen.add(deduplication_key)
        current = grouped.setdefault(
            key,
            {
                "dataset_name": name,
                "normalized_name": key,
                "cargos": set(),
                "parties": set(),
                "ufs": set(),
                "hearing_ids": set(),
                "sources": set(),
                "opinion_count": 0,
            },
        )
        current["cargos"].add(cargo)
        current["hearing_ids"].add(hearing_id)
        current["sources"].add(origin)
        current["opinion_count"] += len(opinions)
        if parsed["party"]:
            current["parties"].add(parsed["party"])
        if parsed["uf"]:
            current["ufs"].add(parsed["uf"])

    rows = []
    for value in grouped.values():
        rows.append(
            {
                "dataset_name": value["dataset_name"],
                "normalized_name": value["normalized_name"],
                "cargos": sorted(value["cargos"]),
                "parties": sorted(value["parties"]),
                "ufs": sorted(value["ufs"]),
                "hearing_ids": sorted(value["hearing_ids"]),
                "hearing_count": len(value["hearing_ids"]),
                "opinion_count": value["opinion_count"],
                "sources": sorted(value["sources"]),
            }
        )
    rows.sort(
        key=lambda row: (-row["opinion_count"], -row["hearing_count"], row["dataset_name"])
    )
    if limit is not None:
        rows = rows[:limit]
    return {
        "generated_at": utc_now_iso(),
        "source": source,
        "total_deputies": len(rows),
        "deputies": rows,
    }


def _candidate_score(deputy: dict[str, Any], candidate: dict[str, Any]) -> float:
    expected_name = deputy["normalized_name"]
    candidate_name = normalize_text(candidate.get("nome"))
    weighted_total = 0.8
    weighted_score = 0.8 * SequenceMatcher(None, expected_name, candidate_name).ratio()

    expected_ufs = {normalize_text(value) for value in deputy.get("ufs", [])}
    if expected_ufs:
        weighted_total += 0.1
        if normalize_text(candidate.get("siglaUf")) in expected_ufs:
            weighted_score += 0.1

    expected_parties = {normalize_text(value) for value in deputy.get("parties", [])}
    if expected_parties:
        weighted_total += 0.1
        if normalize_text(candidate.get("siglaPartido")) in expected_parties:
            weighted_score += 0.1
    return round(weighted_score / weighted_total, 6)


def resolve_deputies(
    extraction: dict[str, Any],
    client: DeputySearchClient,
    legislature: int | None = 57,
    minimum_score: float = 0.86,
    minimum_margin: float = 0.05,
) -> dict[str, Any]:
    """Liga nomes do dataset a IDs oficiais usando nome, UF, partido e margem mínima.

    Correspondências inseguras são preservadas como ``ambiguous`` ou ``unmatched``
    e não seguem automaticamente para a coleta de votos.
    """

    resolved: list[dict[str, Any]] = []
    status_counts: defaultdict[str, int] = defaultdict(int)
    for deputy in extraction.get("deputies", []):
        candidates = client.search_deputies(deputy["dataset_name"], legislature)
        ranked = [
            {"score": _candidate_score(deputy, candidate), **candidate}
            for candidate in candidates
        ]
        ranked.sort(key=lambda value: value["score"], reverse=True)
        best = ranked[0] if ranked else None
        margin = best["score"] - ranked[1]["score"] if len(ranked) > 1 else 1.0
        if best and best["score"] >= minimum_score and margin >= minimum_margin:
            status = "matched"
            camara = best
        elif ranked:
            status = "ambiguous"
            camara = None
        else:
            status = "unmatched"
            camara = None
        status_counts[status] += 1
        resolved.append(
            {
                **deputy,
                "resolution_status": status,
                "camara": camara,
                "candidate_margin": round(margin, 6) if best else None,
                "candidates": ranked[:5],
            }
        )
    return {
        "generated_at": utc_now_iso(),
        "legislature": legislature,
        "minimum_score": minimum_score,
        "minimum_margin": minimum_margin,
        "status_counts": dict(sorted(status_counts.items())),
        "deputies": resolved,
    }
