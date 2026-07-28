from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from planner_core.config import get_settings  # noqa: E402
from server.knowledge_retrieval.embeddings.deterministic import (  # noqa: E402
    DeterministicEmbeddingProvider,
)
from server.knowledge_retrieval.embeddings.openai_compatible import (  # noqa: E402
    OpenAICompatibleEmbeddingProvider,
)
from server.knowledge_retrieval.enums import KnowledgeCategory  # noqa: E402
from server.knowledge_retrieval.errors import KnowledgeCorpusError  # noqa: E402
from server.knowledge_retrieval.index_service import (  # noqa: E402
    DEFAULT_CORPUS_MANIFEST,
    DEFAULT_INDEX_ROOT,
    KnowledgeIndexService,
)
from server.knowledge_retrieval.retrieval_schemas import (  # noqa: E402
    KnowledgeRetrievalRequest,
)
from server.knowledge_retrieval.retriever import (  # noqa: E402
    TrainingKnowledgeRetriever,
)


def _relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError(
            "Paths must be repository-relative without traversal."
        )
    return path


def _configured_index_root() -> Path:
    return _relative_path(get_settings().knowledge_index_runtime_directory)


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--corpus-manifest",
        type=_relative_path,
        default=DEFAULT_CORPUS_MANIFEST,
    )
    parser.add_argument(
        "--index-dir",
        type=_relative_path,
        default=_configured_index_root(),
    )
    parser.add_argument("--json", action="store_true", dest="json_output")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and query a local Training Knowledge vector index."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build")
    _common(build)
    build.add_argument(
        "--provider",
        choices=["deterministic_test", "openai_compatible"],
        default="deterministic_test",
    )
    build.add_argument("--dimensions", type=int, default=64)
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--force", action="store_true")

    validate = commands.add_parser("validate")
    _common(validate)
    validate.add_argument("--index-id")

    list_parser = commands.add_parser("list")
    _common(list_parser)

    query = commands.add_parser("query")
    _common(query)
    query.add_argument("--index-id")
    query.add_argument(
        "--provider",
        choices=["deterministic_test", "openai_compatible"],
        default="deterministic_test",
    )
    query.add_argument("--dimensions", type=int, default=64)
    query.add_argument("--text", required=True)
    query.add_argument("--top-k", type=int, default=4)
    query.add_argument(
        "--category",
        action="append",
        choices=[item.value for item in KnowledgeCategory],
        default=[],
    )
    query.add_argument("--tag", action="append", default=[])
    query.add_argument("--language")
    query.add_argument("--min-score", type=float)

    inspect = commands.add_parser("inspect")
    _common(inspect)
    inspect.add_argument("--index-id", required=True)
    return parser


def _service(args: argparse.Namespace) -> KnowledgeIndexService:
    return KnowledgeIndexService(
        repository_root=REPOSITORY_ROOT,
        corpus_manifest_path=args.corpus_manifest,
        index_root=args.index_dir,
    )


def _provider(name: str, dimensions: int):
    if name == "deterministic_test":
        return DeterministicEmbeddingProvider(
            dimensions=dimensions,
            environment=get_settings().app_env,
        )
    return OpenAICompatibleEmbeddingProvider(get_settings())


def _json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def _run_build(args: argparse.Namespace) -> None:
    result = _service(args).build(
        _provider(args.provider, args.dimensions),
        dry_run=args.dry_run,
        force=args.force,
    )
    if args.json_output:
        _json(result)
        return
    if args.dry_run:
        print(
            f"Index dry-run: {result.chunk_count} chunks, "
            f"{result.estimated_batches} batches, provider={result.provider}, "
            f"model={result.model}, dimensions={result.dimensions or 'provider-defined'}."
        )
        print(f"Corpus root hash: {result.corpus_root_hash}")
        return
    state = "unchanged" if result.unchanged else "written"
    print(f"Index {state}: {result.relative_path}")
    print(f"Index ID: {result.manifest.index_id}")
    print(f"Root hash: {result.manifest.root_hash}")


def _run_validate(args: argparse.Namespace) -> None:
    service = _service(args)
    index_id = args.index_id or service.latest_index_id()
    manifest = service.validate(index_id)
    if args.json_output:
        _json(manifest)
    else:
        print(
            f"Index valid: {manifest.index_id}, {manifest.chunk_count} chunks, "
            f"{manifest.embedding_dimensions} dimensions."
        )
        print(f"Root hash: {manifest.root_hash}")


def _run_list(args: argparse.Namespace) -> None:
    items = _service(args).list_indexes()
    if args.json_output:
        _json([item.model_dump(mode="json") for item in items])
        return
    print("INDEX ID | PROVIDER | MODEL | DIMENSIONS | CHUNKS | ROOT HASH")
    for item in items:
        print(
            f"{item.index_id} | {item.embedding_provider} | "
            f"{item.embedding_model} | {item.embedding_dimensions} | "
            f"{item.chunk_count} | {item.root_hash}"
        )


def _run_query(args: argparse.Namespace) -> None:
    service = _service(args)
    retriever = TrainingKnowledgeRetriever(
        index_service=service,
        provider=_provider(args.provider, args.dimensions),
        index_id=args.index_id,
    )
    response = retriever.retrieve(
        KnowledgeRetrievalRequest(
            query=args.text,
            top_k=args.top_k,
            categories=[
                KnowledgeCategory(value) for value in args.category
            ],
            tags=args.tag,
            language=args.language,
            min_score=args.min_score,
        )
    )
    _json(response)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            _run_build(args)
        elif args.command == "validate":
            _run_validate(args)
        elif args.command == "list":
            _run_list(args)
        elif args.command == "query":
            _run_query(args)
        else:
            _json(_service(args).inspect(args.index_id))
    except KnowledgeCorpusError as exc:
        print(f"Knowledge index error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
