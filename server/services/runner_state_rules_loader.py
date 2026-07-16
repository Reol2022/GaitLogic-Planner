from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from server.domain.runner_state_rules import RunnerStateRules

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "config" / "training" / "runner_state_rules_v1.yaml"


class RunnerStateRulesConfigurationError(RuntimeError):
    """Raised when the versioned runner-state rules cannot be loaded safely."""


def load_runner_state_rules(path: Path | None = None) -> RunnerStateRules:
    rules_path = (path or DEFAULT_RULES_PATH).resolve()
    try:
        raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RunnerStateRulesConfigurationError(f"Unable to load runner-state rules from {rules_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise RunnerStateRulesConfigurationError(f"Runner-state rules must be a YAML object: {rules_path}")
    try:
        return RunnerStateRules.model_validate(raw)
    except ValidationError as exc:
        raise RunnerStateRulesConfigurationError(f"Invalid runner-state rules in {rules_path}: {exc}") from exc


@lru_cache(maxsize=1)
def get_runner_state_rules() -> RunnerStateRules:
    return load_runner_state_rules()
