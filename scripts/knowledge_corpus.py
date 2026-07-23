from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from server.knowledge_retrieval.corpus_service import (  # noqa: E402
    DEFAULT_MANIFEST_PATH,
    KnowledgeCorpusService,
)
from server.knowledge_retrieval.errors import KnowledgeCorpusError  # noqa: E402


def _safe_relative_path(value: str, *, option: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError(
            f"{option} must be a repository-relative path without traversal."
        )
    return path


def _root_path(value: str) -> Path:
    return _safe_relative_path(value, option="--root")


def _output_path(value: str) -> Path:
    return _safe_relative_path(value, option="--output")


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=_root_path, default=Path("knowledge"))
    parser.add_argument(
        "--output",
        type=_output_path,
        default=DEFAULT_MANIFEST_PATH,
    )
    parser.add_argument("--include-draft", action="store_true")
    parser.add_argument("--include-deprecated", action="store_true")
    parser.add_argument("--json", action="store_true", dest="json_output")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and build the deterministic training knowledge corpus."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    _add_common_options(validate_parser)

    build_parser = subparsers.add_parser("build")
    _add_common_options(build_parser)
    build_parser.add_argument("--dry-run", action="store_true")
    build_parser.add_argument("--force", action="store_true")

    list_parser = subparsers.add_parser("list")
    _add_common_options(list_parser)

    inspect_parser = subparsers.add_parser("inspect")
    _add_common_options(inspect_parser)
    target = inspect_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--document-id")
    target.add_argument("--chunk-id")
    return parser


def _service(args: argparse.Namespace) -> KnowledgeCorpusService:
    return KnowledgeCorpusService(
        args.root,
        repository_root=REPOSITORY_ROOT,
        output_path=args.output,
    )


def _dump_json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _run_validate(args: argparse.Namespace) -> None:
    manifest = _service(args).validate()
    result = {
        "valid": True,
        "root_hash": manifest.root_hash,
        "schema_version": manifest.schema_version,
        "corpus_version": manifest.corpus_version,
        "statistics": manifest.statistics.model_dump(mode="json"),
    }
    if args.json_output:
        _dump_json(result)
        return
    statistics = manifest.statistics
    print(
        "Corpus valid: "
        f"{statistics.document_count} documents, "
        f"{statistics.source_count} sources, "
        f"{statistics.chunk_count} chunks."
    )
    print(f"Root hash: {manifest.root_hash}")


def _run_build(args: argparse.Namespace) -> None:
    result = _service(args).build(
        dry_run=args.dry_run,
        force=args.force,
        include_draft=args.include_draft,
        include_deprecated=args.include_deprecated,
    )
    if args.json_output:
        _dump_json(result)
        return
    state = "dry-run" if result.dry_run else (
        "unchanged" if result.unchanged else "written"
    )
    print(f"Manifest {state}: {result.output_path}")
    print(f"Root hash: {result.manifest.root_hash}")
    print(
        "Statistics: "
        f"{result.manifest.statistics.document_count} documents, "
        f"{result.manifest.statistics.chunk_count} chunks."
    )


def _run_list(args: argparse.Namespace) -> None:
    items = _service(args).list_documents(
        include_draft=args.include_draft,
        include_deprecated=args.include_deprecated,
    )
    if args.json_output:
        _dump_json(
            [item.model_dump(mode="json", exclude_none=True) for item in items]
        )
        return
    print("DOCUMENT ID | CATEGORY | STATUS | VERSION | CHUNKS | SOURCE | TITLE")
    for item in items:
        print(
            f"{item.document_id} | {item.category.value} | {item.status.value} | "
            f"{item.knowledge_version} | {item.chunk_count} | "
            f"{item.source_id} | {item.title}"
        )


def _run_inspect(args: argparse.Namespace) -> None:
    service = _service(args)
    options = {
        "include_draft": args.include_draft,
        "include_deprecated": args.include_deprecated,
    }
    if args.document_id:
        result = service.inspect_document(args.document_id, **options)
    else:
        result = service.inspect_chunk(args.chunk_id, **options)
    _dump_json(result)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            _run_validate(args)
        elif args.command == "build":
            _run_build(args)
        elif args.command == "list":
            _run_list(args)
        else:
            _run_inspect(args)
    except KnowledgeCorpusError as exc:
        print(f"Knowledge corpus error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
