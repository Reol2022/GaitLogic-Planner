from __future__ import annotations

import json
from pathlib import Path

from server.agent.evaluation_regression.schemas import EvaluationBaselineManifest


class EvaluationBaselineError(ValueError):
    """Raised when the versioned public baseline cannot be safely loaded."""


def load_baseline(path: Path) -> EvaluationBaselineManifest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationBaselineError("Public evaluation baseline is unavailable.") from exc
    try:
        return EvaluationBaselineManifest.model_validate(payload)
    except ValueError as exc:
        raise EvaluationBaselineError("Public evaluation baseline is invalid.") from exc
