"""Leitura, validação estrutural e auditoria do dataset PublicHearingBR local."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


class DatasetValidationError(ValueError):
    """Indica uma linha invalida em um dos arquivos PublicHearingBR."""


@dataclass(frozen=True)
class DatasetPaths:
    """Resolve os dois arquivos JSONL esperados dentro da pasta do dataset."""

    directory: Path

    @property
    def lds(self) -> Path:
        return self.directory / "PublicHearingBR_LDS.jsonl"

    @property
    def nli(self) -> Path:
        return self.directory / "PublicHearingBR_NLI.jsonl"

    def require_files(self) -> None:
        missing = [str(path) for path in (self.lds, self.nli) if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"Arquivo(s) do dataset ausente(s): {', '.join(missing)}")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Percorre um JSONL e informa arquivo e linha quando encontra JSON inválido."""

    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise DatasetValidationError(
                    f"JSON invalido em {path}:{line_number}: {error.msg}"
                ) from error
            if not isinstance(value, dict):
                raise DatasetValidationError(
                    f"Era esperado um objeto em {path}:{line_number}"
                )
            yield value


def _require(record: dict[str, Any], keys: tuple[str, ...], source: str) -> None:
    missing = [key for key in keys if key not in record]
    if missing:
        raise DatasetValidationError(
            f"Campos ausentes em {source}: {', '.join(missing)}"
        )


def iter_lds(paths: DatasetPaths) -> Iterator[dict[str, Any]]:
    """Produz registros LDS após validar seus campos estruturais mínimos."""

    for record in iter_jsonl(paths.lds):
        _require(record, ("id", "materia", "transcricao", "metadados"), "LDS")
        metadata = record["metadados"]
        if not isinstance(metadata, dict):
            raise DatasetValidationError("O campo metadados do LDS deve ser um objeto")
        _require(metadata, ("assunto", "envolvidos"), "LDS.metadados")
        if not isinstance(metadata["envolvidos"], list):
            raise DatasetValidationError("LDS.metadados.envolvidos deve ser uma lista")
        yield record


def iter_nli(paths: DatasetPaths) -> Iterator[dict[str, Any]]:
    """Produz registros NLI após validar metadados, envolvidos e opiniões."""

    for record in iter_jsonl(paths.nli):
        _require(record, ("id", "metadados_extraidos"), "NLI")
        metadata = record["metadados_extraidos"]
        if not isinstance(metadata, dict):
            raise DatasetValidationError(
                "O campo metadados_extraidos do NLI deve ser um objeto"
            )
        _require(metadata, ("assunto", "envolvidos"), "NLI.metadados_extraidos")
        if not isinstance(metadata["envolvidos"], list):
            raise DatasetValidationError(
                "NLI.metadados_extraidos.envolvidos deve ser uma lista"
            )
        yield record


def audit_dataset(paths: DatasetPaths) -> dict[str, Any]:
    """Resume volumes, rótulos de verificação e anomalias dos arquivos locais."""

    paths.require_files()
    lds_count = 0
    lds_people = 0
    lds_opinions = 0
    lds_ids: set[Any] = set()
    for record in iter_lds(paths):
        lds_count += 1
        lds_ids.add(record["id"])
        people = record["metadados"]["envolvidos"]
        lds_people += len(people)
        lds_opinions += sum(len(person.get("opinioes", [])) for person in people)

    nli_count = 0
    nli_people = 0
    nli_opinions = 0
    nli_ids: set[Any] = set()
    labels: Counter[str] = Counter()
    chunk_counts: Counter[int] = Counter()
    anomalies: list[dict[str, Any]] = []
    for record in iter_nli(paths):
        nli_count += 1
        nli_ids.add(record["id"])
        people = record["metadados_extraidos"]["envolvidos"]
        nli_people += len(people)
        for person in people:
            for opinion in person.get("opinioes", []):
                nli_opinions += 1
                verification = opinion.get("verificacao_alucinacao", {})
                manual = verification.get("verificacao_manual")
                labels[str(manual).lower()] += 1
                chunks = opinion.get("chunks_proximos", [])
                chunk_counts[len(chunks)] += 1
                if len(chunks) != 4:
                    anomalies.append(
                        {
                            "id": record["id"],
                            "nome": person.get("nome"),
                            "opiniao": opinion.get("opiniao"),
                            "quantidade_chunks": len(chunks),
                        }
                    )

    return {
        "lds": {
            "audiencias": lds_count,
            "pessoas": lds_people,
            "opinioes": lds_opinions,
        },
        "nli": {
            "audiencias": nli_count,
            "pessoas": nli_people,
            "opinioes": nli_opinions,
            "rotulos_verificacao_manual": dict(sorted(labels.items())),
            "quantidade_chunks": {
                str(key): value for key, value in sorted(chunk_counts.items())
            },
        },
        "ids_coincidem": lds_ids == nli_ids,
        "ids_apenas_lds": sorted(lds_ids - nli_ids),
        "ids_apenas_nli": sorted(nli_ids - lds_ids),
        "anomalias_chunks": anomalies,
    }
