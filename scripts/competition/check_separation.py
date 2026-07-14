#!/usr/bin/env python3
"""Read-only validation for product and private competition workspace separation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_git(path: Path, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return result.returncode, result.stdout.strip()


def main() -> int:
    product = Path(__file__).resolve().parents[2]
    private = product.parent / "gaitlogic-competition-2026"
    failures: list[str] = []
    warnings: list[str] = []
    if private == product or product in private.parents:
        failures.append("private workspace must be outside the product repository")
    if not (product / ".git").exists():
        failures.append("product repository has no .git directory")
    if not private.exists():
        failures.append(f"private workspace is missing: {private}")
    elif not (private / ".git").exists():
        failures.append("private workspace is not an independent Git repository")
    else:
        code, remote = run_git(private, "remote")
        if code or remote:
            failures.append("private workspace must not have a remote during initialization")
        if run_git(product, "ls-files", "--", str(private))[1]:
            failures.append("product repository tracks content from private workspace")
        manifest = private / "competition-manifest.yaml"
        if not manifest.exists():
            failures.append("private workspace lacks competition-manifest.yaml")
        else:
            commit = next(
                (
                    line.split(":", 1)[1].strip().strip('"\'')
                    for line in manifest.read_text(encoding="utf-8").splitlines()
                    if line.strip().startswith("commit:")
                ),
                "",
            )
            if not commit:
                warnings.append("manifest product commit is not yet recorded")
            elif run_git(product, "cat-file", "-e", f"{commit}^{{commit}}")[0]:
                failures.append("manifest references a product commit that does not exist locally")
    defaults = {"COMPETITION_MODE": "false", "ENABLE_EXPERIMENT_DASHBOARD": "false", "ENABLE_EXPERIMENT_DASHBOARD": "false", "ENABLE_AGENT_TRACE": "false", "ENABLE_SURVEY_MODULE": "false", "ENABLE_COMPETITION_DEMO_DATA": "false"}
    text = (product / ".env.example").read_text(encoding="utf-8")
    for key, value in defaults.items():
        if f"{key}={value}" not in text:
            failures.append(f".env.example must default {key}={value}")
    for message in warnings:
        print(f"WARNING: {message}")
    for message in failures:
        print(f"FAIL: {message}")
    if failures:
        return 2
    print("PASS: product and competition workspaces are separated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
