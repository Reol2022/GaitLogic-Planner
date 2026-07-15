from __future__ import annotations

import re
from typing import Any

from planner_core.training_knowledge.condition_evaluator import read_field
from planner_core.training_knowledge.operators import MISSING
from planner_core.training_knowledge.schemas import FIELD_PATH_PATTERN

PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)*)\}")
MISSING_PLACEHOLDER = "N/A"


def render_explanation(template: str, facts: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        path = match.group(1)
        if not FIELD_PATH_PATTERN.match(path):
            return MISSING_PLACEHOLDER
        value = read_field(facts, path)
        if value is MISSING or value is None:
            return MISSING_PLACEHOLDER
        return str(value)

    return PLACEHOLDER_PATTERN.sub(replace, template)


def find_invalid_placeholders(template: str) -> list[str]:
    invalid: list[str] = []
    for raw in re.findall(r"\{([^{}]+)\}", template):
        if not FIELD_PATH_PATTERN.match(raw):
            invalid.append(raw)
    return invalid

