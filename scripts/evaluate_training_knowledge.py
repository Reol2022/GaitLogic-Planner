#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

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
from server.knowledge_retrieval.evaluation.datasets import (  # noqa: E402
    load_rag_dataset,
    load_retrieval_dataset,
)
from server.knowledge_retrieval.evaluation.report import write_report  # noqa: E402
from server.knowledge_retrieval.evaluation.runner import (  # noqa: E402
    TrainingKnowledgeEvaluationRunner,
)
from server.knowledge_retrieval.evaluation.schemas import EvaluationMode  # noqa: E402

DEFAULT_RETRIEVAL_DATASET = Path(
    "docs/rag/evaluation/cases/retrieval-eval-v1.json"
)
DEFAULT_RAG_DATASET = Path("docs/rag/evaluation/cases/rag-answer-eval-v1.json")
DEFAULT_RESULTS = Path("docs/rag/evaluation/results")


def _relative(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise argparse.ArgumentTypeError("paths must be repository-relative")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run safe Training Knowledge retrieval and RAG evaluations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("retrieval", "rag", "all"):
        item = subparsers.add_parser(command)
        item.add_argument(
            "--provider",
            choices=(
                ["deterministic_test", "openai_compatible"]
                if command == "retrieval"
                else ["fake", "openai_compatible"]
            ),
            default="deterministic_test" if command == "retrieval" else "fake",
        )
        item.add_argument(
            "--mode",
            choices=[mode.value for mode in EvaluationMode],
            default=(
                EvaluationMode.DENSE_WITH_METADATA.value
                if command == "retrieval"
                else EvaluationMode.FULL_SYSTEM.value
            ),
        )
        item.add_argument("--index-id")
        item.add_argument(
            "--retrieval-dataset",
            "--dataset",
            type=_relative,
            default=DEFAULT_RETRIEVAL_DATASET,
        )
        item.add_argument("--rag-dataset", type=_relative, default=DEFAULT_RAG_DATASET)
        item.add_argument("--output-dir", type=_relative, default=DEFAULT_RESULTS)
        item.add_argument("--dry-run", action="store_true")
        item.add_argument("--json", action="store_true", dest="json_output")
    return parser


def _resolved(path: Path) -> Path:
    resolved = (REPOSITORY_ROOT / path).resolve()
    resolved.relative_to(REPOSITORY_ROOT)
    return resolved


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    retrieval_dataset = _resolved(args.retrieval_dataset)
    rag_dataset = _resolved(args.rag_dataset)
    if args.dry_run:
        payload: dict[str, object] = {"dry_run": True}
        if args.command in {"retrieval", "all"}:
            payload["retrieval_cases"] = len(
                load_retrieval_dataset(
                    retrieval_dataset,
                    corpus_manifest_path=REPOSITORY_ROOT
                    / "knowledge/manifests/corpus-v1.json",
                ).cases
            )
        if args.command in {"rag", "all"}:
            payload["rag_cases"] = len(load_rag_dataset(rag_dataset).cases)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    runner = TrainingKnowledgeEvaluationRunner(repository_root=REPOSITORY_ROOT)
    reports = []
    mode = EvaluationMode(args.mode)
    if args.command in {"retrieval", "all"}:
        provider_name = (
            args.provider if args.command == "retrieval" else "deterministic_test"
        )
        settings = get_settings()
        if provider_name == "deterministic_test":
            factory = lambda: DeterministicEmbeddingProvider(
                dimensions=64, environment=settings.app_env
            )
            model = "deterministic-sha256-v1"
            real = False
        else:
            factory = lambda: OpenAICompatibleEmbeddingProvider(get_settings())
            model = settings.knowledge_embedding_model
            real = True
        reports.append(
            runner.run_retrieval(
                dataset_path=retrieval_dataset,
                provider_factory=factory,
                provider_name=provider_name,
                model_name=model,
                mode=mode,
                index_id=args.index_id,
                real_provider=real,
            )
        )
    if args.command in {"rag", "all"}:
        provider_name = args.provider if args.command == "rag" else "fake"
        if provider_name == "openai_compatible":
            reports.append(
                runner.run_rag_real(
                    dataset_path=rag_dataset,
                    settings=get_settings(),
                    mode=mode,
                )
            )
        else:
            reports.append(
                runner.run_rag(
                    dataset_path=rag_dataset,
                    mode=mode,
                    provider_name="fake",
                )
            )
    output = _resolved(args.output_dir)
    for report in reports:
        stem = (
            "training-knowledge-retrieval-eval-v1"
            if report.evaluation_kind == "retrieval"
            else "training-knowledge-rag-eval-v1"
        )
        write_report(
            report,
            json_path=output / f"{stem}.json",
            markdown_path=output / f"{stem}.md",
        )
        print(
            f"{report.evaluation_kind}: {report.case_count} cases, "
            f"{len(report.failure_case_ids)} failures"
        )
        if args.json_output:
            print(json.dumps(report.metrics, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
