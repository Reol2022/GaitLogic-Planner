from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from server.agent.competition_ablation.schemas import CompetitionAblationCase


def load_ablation_cases(path: Path) -> list[CompetitionAblationCase]:
    if not path.is_file():
        raise FileNotFoundError(f"Competition ablation case set is missing: {path}")
    cases: list[CompetitionAblationCase] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            case = CompetitionAblationCase.model_validate_json(raw)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid ablation case at line {line_number}") from exc
        if case.case_id in seen:
            raise ValueError(f"Duplicate ablation case_id: {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    if not 24 <= len(cases) <= 36:
        raise ValueError("Competition ablation case set must contain 24 to 36 cases")
    return cases

