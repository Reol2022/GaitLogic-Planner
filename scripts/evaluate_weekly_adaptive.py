#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.weekly_review_evaluation import load_cases, run_evaluation, write_report


def main() -> int:
    report = run_evaluation(load_cases(ROOT / "evaluation/weekly_adaptive/cases_v1.jsonl"))
    write_report(
        report,
        ROOT / "docs/weekly-review/evaluation/weekly-adaptive-eval-v1.json",
        ROOT / "docs/weekly-review/evaluation/weekly-adaptive-eval-v1.md",
    )
    summary = report["summary"]
    print(f"Cases: {summary['passed_cases']}/{summary['total_cases']}")
    return 0 if summary["passed_cases"] == summary["total_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
