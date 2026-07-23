from pathlib import Path

import pytest

from server.agent.evaluation.loader import EvaluationCaseLoadError, load_evaluation_cases
from tests.test_agent_evaluation_schemas import valid_case


def write_cases(path: Path, payloads: list[dict]) -> None:
    import json

    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in payloads),
        encoding="utf-8",
    )


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    write_cases(path, [valid_case(), valid_case()])
    with pytest.raises(EvaluationCaseLoadError, match="duplicate"):
        load_evaluation_cases(path)


def test_loader_rejects_unknown_fixture(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    write_cases(path, [{**valid_case(), "fixture": "not_registered"}])
    with pytest.raises(EvaluationCaseLoadError, match="unknown fixture"):
        load_evaluation_cases(path)


def test_loader_reports_invalid_json_line(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(EvaluationCaseLoadError, match="line 1"):
        load_evaluation_cases(path)
