"""Build, validate, and query the local deterministic BM25 knowledge index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner_core.config import get_settings  # noqa: E402
from server.knowledge_retrieval.enums import KnowledgeCategory  # noqa: E402
from server.knowledge_retrieval.errors import KnowledgeCorpusError  # noqa: E402
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest  # noqa: E402
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService  # noqa: E402
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever  # noqa: E402


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("Paths must be repository-relative without traversal.")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a deterministic local BM25 knowledge index.")
    parser.add_argument("command", choices=("build", "validate", "query"))
    parser.add_argument("--index-dir", type=_relative, default=Path(get_settings().knowledge_bm25_index_runtime_directory))
    parser.add_argument("--index-id")
    parser.add_argument("--text")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--category", action="append", choices=[item.value for item in KnowledgeCategory], default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--language")
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _write(value: object, json_output: bool) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if json_output:
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    service = Bm25IndexService(repository_root=ROOT, index_root=args.index_dir)
    try:
        if args.command == "build":
            _write(service.build(), args.json_output)
        elif args.command == "validate":
            _write(service.validate(args.index_id or service.latest_index_id()), args.json_output)
        else:
            if not args.text:
                raise ValueError("--text is required for query")
            response = TrainingKnowledgeBm25Retriever(
                index_service=service, index_id=args.index_id or service.latest_index_id()
            ).retrieve(KnowledgeRetrievalRequest(
                query=args.text, top_k=args.top_k,
                categories=[KnowledgeCategory(item) for item in args.category],
                tags=args.tag, language=args.language,
            ))
            _write(response, args.json_output)
    except (KnowledgeCorpusError, ValueError) as exc:
        print(f"BM25 index error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
