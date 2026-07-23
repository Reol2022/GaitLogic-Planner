from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from server.agent.evaluation.fixtures import EVALUATION_FIXTURES
from server.agent.evaluation.schemas import CoachEvaluationCase


class EvaluationCaseLoadError(ValueError):
    """Raised when the public, versioned evaluation case set is invalid."""


def load_evaluation_cases(path: str | Path) -> list[CoachEvaluationCase]:
    source = Path(path)
    cases: list[CoachEvaluationCase] = []
    seen: set[str] = set()
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvaluationCaseLoadError(f"cannot read case set: {source}") from exc
    for line_number, raw in enumerate(lines, start=1):
        if not raw.strip():
            continue
        try:
            case = CoachEvaluationCase.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError) as exc:
            raise EvaluationCaseLoadError(
                f"invalid evaluation case at line {line_number}"
            ) from exc
        if case.case_id in seen:
            raise EvaluationCaseLoadError(f"duplicate case_id: {case.case_id}")
        if case.fixture not in EVALUATION_FIXTURES:
            raise EvaluationCaseLoadError(
                f"unknown fixture for {case.case_id}: {case.fixture}"
            )
        seen.add(case.case_id)
        cases.append(case)
    if not cases:
        raise EvaluationCaseLoadError("evaluation case set is empty")
    return cases
