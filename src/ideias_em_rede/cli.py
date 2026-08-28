"""Interface de linha de comando que orquestra as oito etapas do projeto."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .alignment import run_party_alignment
from .camara import CamaraClient
from .comparison import run_comparison
from .dataset import DatasetPaths, audit_dataset
from .deputies import extract_deputies, resolve_deputies
from .io_utils import read_json, write_json, write_jsonl
from .pipeline import collect_votes_and_orientations
from .positions import (
    OpenAIResponsesClassifier,
    prepare_position_candidates,
    run_position_extraction,
)
from .web_export import export_dashboard_data


DEFAULT_DATASET = Path("PublicHearingBR")
DEFAULT_PROCESSED = Path("data/processed")


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _client(args: argparse.Namespace) -> CamaraClient:
    return CamaraClient(
        cache_dir=None if args.no_cache else Path(args.cache_dir),
        timeout=args.timeout,
    )


def _add_client_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cache-dir", default="data/cache/camara")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)


def build_parser() -> argparse.ArgumentParser:
    """Declara comandos, opções e caminhos padrão da aplicação."""

    parser = argparse.ArgumentParser(
        prog="ideias-em-rede",
        description="PublicHearingBR + API de Dados Abertos da Camara",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Valida e resume o dataset local")
    audit.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)

    extract = subparsers.add_parser("extract", help="Extrai deputados do dataset")
    extract.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    extract.add_argument("--source", choices=("lds", "nli", "both"), default="lds")
    extract.add_argument("--limit", type=int)
    extract.add_argument(
        "--output", type=Path, default=DEFAULT_PROCESSED / "deputados_extraidos.json"
    )

    resolve = subparsers.add_parser("resolve", help="Resolve IDs na API da Camara")
    resolve.add_argument(
        "--input", type=Path, default=DEFAULT_PROCESSED / "deputados_extraidos.json"
    )
    resolve.add_argument(
        "--output", type=Path, default=DEFAULT_PROCESSED / "deputados_resolvidos.json"
    )
    resolve.add_argument("--legislature", type=int, default=57)
    resolve.add_argument("--minimum-score", type=float, default=0.86)
    resolve.add_argument("--minimum-margin", type=float, default=0.05)
    _add_client_arguments(resolve)

    collect = subparsers.add_parser("collect", help="Coleta votos e orientacoes")
    collect.add_argument(
        "--input", type=Path, default=DEFAULT_PROCESSED / "deputados_resolvidos.json"
    )
    collect.add_argument("--start-date", required=True)
    collect.add_argument("--end-date", required=True)
    collect.add_argument(
        "--output-dir", type=Path, default=DEFAULT_PROCESSED / "camara"
    )
    collect.add_argument("--max-votings", type=int)
    collect.add_argument("--organ")
    collect.add_argument("--workers", type=int, default=4)
    _add_client_arguments(collect)

    alignment = subparsers.add_parser(
        "alignment", help="Calcula o alinhamento entre voto e orientacao partidaria"
    )
    alignment.add_argument(
        "--votes", type=Path, default=DEFAULT_PROCESSED / "camara/votos.jsonl"
    )
    alignment.add_argument(
        "--orientations",
        type=Path,
        default=DEFAULT_PROCESSED / "camara/orientacoes.jsonl",
    )
    alignment.add_argument(
        "--votings", type=Path, default=DEFAULT_PROCESSED / "camara/votacoes.jsonl"
    )
    alignment.add_argument(
        "--output-dir", type=Path, default=DEFAULT_PROCESSED / "analysis"
    )

    prepare_positions = subparsers.add_parser(
        "prepare-positions", help="Prepara falas rastreaveis para classificacao por LLM"
    )
    prepare_positions.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    prepare_positions.add_argument(
        "--resolution",
        type=Path,
        default=DEFAULT_PROCESSED / "deputados_resolvidos.json",
    )
    prepare_positions.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PROCESSED / "analysis/posicoes_candidatas.jsonl",
    )
    prepare_positions.add_argument("--limit", type=int, default=24)
    prepare_positions.add_argument("--per-deputy", type=int, default=2)
    prepare_positions.add_argument("--hearing-id", type=int, action="append")

    extract_positions = subparsers.add_parser(
        "extract-positions", help="Classifica as posicoes das falas com a API da OpenAI"
    )
    extract_positions.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_PROCESSED / "analysis/posicoes_candidatas.jsonl",
    )
    extract_positions.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PROCESSED / "analysis/posicoes_llm.jsonl",
    )
    extract_positions.add_argument("--model", default="gpt-5-mini")
    extract_positions.add_argument("--api-key-env", default="OPENAI_API_KEY")
    extract_positions.add_argument("--cache-dir", type=Path, default=Path("data/cache/openai"))
    extract_positions.add_argument("--timeout", type=float, default=90.0)
    extract_positions.add_argument("--retries", type=int, default=2)

    compare = subparsers.add_parser(
        "compare", help="Compara posicoes extraidas com votos de uma amostra configurada"
    )
    compare.add_argument(
        "--positions",
        type=Path,
        default=DEFAULT_PROCESSED / "analysis/posicoes_llm.jsonl",
    )
    compare.add_argument(
        "--votes", type=Path, default=DEFAULT_PROCESSED / "camara/votos.jsonl"
    )
    compare.add_argument(
        "--votings", type=Path, default=DEFAULT_PROCESSED / "camara/votacoes.jsonl"
    )
    compare.add_argument(
        "--config", type=Path, default=Path("config/comparison_sample.json")
    )
    compare.add_argument(
        "--output-dir", type=Path, default=DEFAULT_PROCESSED / "analysis"
    )

    web_data = subparsers.add_parser(
        "web-data", help="Consolida os resultados em JSON para a interface web"
    )
    web_data.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    web_data.add_argument(
        "--output", type=Path, default=Path("web/app/dashboard.json")
    )

    run = subparsers.add_parser("run", help="Executa as etapas 1 a 4")
    run.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET)
    run.add_argument("--source", choices=("lds", "nli", "both"), default="lds")
    run.add_argument("--limit", type=int, default=12)
    run.add_argument("--legislature", type=int, default=57)
    run.add_argument("--start-date", required=True)
    run.add_argument("--end-date", required=True)
    run.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED)
    run.add_argument("--max-votings", type=int)
    run.add_argument("--organ")
    run.add_argument("--workers", type=int, default=4)
    run.add_argument("--minimum-score", type=float, default=0.86)
    run.add_argument("--minimum-margin", type=float, default=0.05)
    _add_client_arguments(run)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Executa o comando solicitado e imprime um resumo JSON legível."""

    args = build_parser().parse_args(argv)
    if args.command == "audit":
        _print(audit_dataset(DatasetPaths(args.dataset_dir)))
        return
    if args.command == "extract":
        result = extract_deputies(
            DatasetPaths(args.dataset_dir), source=args.source, limit=args.limit
        )
        write_json(args.output, result)
        _print({"output": str(args.output), "total_deputies": result["total_deputies"]})
        return
    if args.command == "resolve":
        result = resolve_deputies(
            read_json(args.input),
            _client(args),
            legislature=args.legislature,
            minimum_score=args.minimum_score,
            minimum_margin=args.minimum_margin,
        )
        write_json(args.output, result)
        _print({"output": str(args.output), **result["status_counts"]})
        return
    if args.command == "collect":
        _print(
            collect_votes_and_orientations(
                read_json(args.input),
                _client(args),
                args.start_date,
                args.end_date,
                args.output_dir,
                max_votings=args.max_votings,
                organ=args.organ,
                workers=args.workers,
            )
        )
        return
    if args.command == "alignment":
        _print(
            run_party_alignment(
                args.votes, args.orientations, args.votings, args.output_dir
            )
        )
        return
    if args.command == "prepare-positions":
        candidates = prepare_position_candidates(
            DatasetPaths(args.dataset_dir),
            read_json(args.resolution),
            limit=args.limit,
            per_deputy=args.per_deputy,
            hearing_ids=set(args.hearing_id) if args.hearing_id else None,
        )
        write_jsonl(args.output, candidates)
        _print({"output": str(args.output), "candidates": len(candidates)})
        return
    if args.command == "extract-positions":
        from .alignment import read_jsonl

        classifier = OpenAIResponsesClassifier(
            model=args.model,
            api_key_env=args.api_key_env,
            cache_dir=args.cache_dir,
            timeout=args.timeout,
            retries=args.retries,
        )
        _print(run_position_extraction(read_jsonl(args.input), classifier, args.output))
        return
    if args.command == "compare":
        _print(
            run_comparison(
                args.positions, args.votes, args.votings, args.config, args.output_dir
            )
        )
        return
    if args.command == "web-data":
        dashboard = export_dashboard_data(args.processed_dir, args.output)
        _print(
            {
                "output": str(args.output),
                "deputies": len(dashboard["deputies"]),
                "llm_status": dashboard["llmStatus"],
            }
        )
        return

    paths = DatasetPaths(args.dataset_dir)
    audit_result = audit_dataset(paths)
    extraction = extract_deputies(paths, source=args.source, limit=args.limit)
    extracted_path = args.processed_dir / "deputados_extraidos.json"
    write_json(extracted_path, extraction)
    resolution = resolve_deputies(
        extraction,
        _client(args),
        legislature=args.legislature,
        minimum_score=args.minimum_score,
        minimum_margin=args.minimum_margin,
    )
    resolved_path = args.processed_dir / "deputados_resolvidos.json"
    write_json(resolved_path, resolution)
    collection = collect_votes_and_orientations(
        resolution,
        _client(args),
        args.start_date,
        args.end_date,
        args.processed_dir / "camara",
        max_votings=args.max_votings,
        organ=args.organ,
        workers=args.workers,
    )
    _print(
        {
            "audit": audit_result,
            "extraction": {
                "output": str(extracted_path),
                "total_deputies": extraction["total_deputies"],
            },
            "resolution": {
                "output": str(resolved_path),
                **resolution["status_counts"],
            },
            "collection": collection,
        }
    )


if __name__ == "__main__":
    main()
