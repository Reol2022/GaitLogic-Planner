from __future__ import annotations

import subprocess
import sys


def test_cli_dry_run_validates_both_datasets_without_network() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_training_knowledge.py", "all", "--dry-run"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"retrieval_cases": 60' in result.stdout
    assert '"rag_cases": 36' in result.stdout


def test_cli_rejects_absolute_dataset_paths() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/evaluate_training_knowledge.py",
            "retrieval",
            "--retrieval-dataset",
            "C:/private/cases.json",
            "--dry-run",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "repository-relative" in result.stderr


def test_cli_has_no_api_key_argument() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/evaluate_training_knowledge.py", "retrieval", "--help"],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    assert "--api-key" not in result.stdout
