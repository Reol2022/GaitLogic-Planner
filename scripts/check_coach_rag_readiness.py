from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from planner_core.config import get_settings  # noqa: E402
from server.knowledge_retrieval.readiness import (  # noqa: E402
    CoachRagReadinessService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Coach RAG deployment configuration without calling providers."
        )
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--require-enabled",
        action="store_true",
        help="Treat disabled Coach or knowledge retrieval as a deployment failure.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = CoachRagReadinessService(
        get_settings(),
        repository_root=REPOSITORY_ROOT,
    ).run(require_enabled=args.require_enabled)
    if args.json_output:
        print(
            json.dumps(
                report.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    else:
        print(f"Coach RAG readiness: {'READY' if report.ready else 'NOT READY'}")
        print(f"Exit code: {int(report.exit_code)}")
        print(
            "Features: "
            f"coach={'enabled' if report.coach_enabled else 'disabled'}, "
            f"knowledge={'enabled' if report.knowledge_enabled else 'disabled'}"
        )
        print(
            "Modes: "
            f"chat_provider={report.chat_provider}, "
            f"embedding_provider={report.embedding_provider}, "
            f"thinking={report.thinking_mode}, "
            f"response_format={report.response_format_mode}"
        )
        for check in report.checks:
            print(f"[{check.status}] {check.name}: {check.code}")
    return int(report.exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
