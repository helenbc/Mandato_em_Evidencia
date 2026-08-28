"""Funções pequenas de serialização usadas por todas as etapas do pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now_iso() -> str:
    """Retorna o instante UTC atual no formato ISO 8601."""

    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    """Lê um arquivo JSON UTF-8."""

    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, value: Any) -> None:
    """Grava JSON de forma atômica para evitar arquivos parcialmente escritos."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    """Grava objetos em JSONL de forma atômica e devolve o total de linhas."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False))
            stream.write("\n")
            count += 1
    temporary.replace(path)
    return count
