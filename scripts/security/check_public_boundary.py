#!/usr/bin/env python3
"""Report public-repository boundary violations without modifying files."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

FORBIDDEN_PATH_PARTS = (
    "data/private/", "data/raw/", "data/user-data/", "exports/", "uploads/",
    "survey/raw/", "user-study/raw-data/", "user-study/interviews/raw/",
    "competition/private/", "competition/results/", "competition/videos/",
    "competition/defense/", "docs/competition/private/", "credentials/", "secrets/",
    "tokens/", "garmin_tokens/", "backups/", "database-backups/",
)
PATH_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".dump", ".sqlite", ".sqlite3")
CONTENT_RULES = {
    "OpenAI-style API key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "private key header": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "credential or token literal": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|garmin[_-]?token)\b\s*[:=]\s*['\"][A-Za-z0-9._~+/=-]{16,}['\"]"),
    "database URL with literal password": re.compile(r"(?i)(?:mysql|postgres(?:ql)?|mongodb)://[^\s:/{}]+:[^\s@{}]+@"),
}
PERSONAL_DATA_RULES = {
    "email address": re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    "Chinese mainland phone number": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
}
PERSONAL_DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".txt", ".xlsx", ".xls"}


def git_lines(repo: Path, args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return [line for line in result.stdout.splitlines() if line]


def target_files(repo: Path, all_tracked: bool) -> list[str]:
    return git_lines(repo, ["ls-files"] if all_tracked else ["diff", "--cached", "--name-only"])


def check_files(repo: Path, files: list[str]) -> list[tuple[str, str]]:
    findings: list[tuple[str, str]] = []
    for relative in files:
        normalized = relative.replace("\\", "/").lower()
        if normalized == ".env" or (normalized.startswith(".env.") and normalized != ".env.example"):
            findings.append((relative, "tracked environment file"))
        elif any(part in normalized for part in FORBIDDEN_PATH_PARTS) or normalized.endswith(PATH_SUFFIXES):
            findings.append((relative, "forbidden private-data or credential path"))
        path = repo / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for rule, pattern in CONTENT_RULES.items():
            if pattern.search(text):
                findings.append((relative, rule))
        if path.suffix.lower() in PERSONAL_DATA_SUFFIXES:
            for rule, pattern in PERSONAL_DATA_RULES.items():
                if pattern.search(text):
                    findings.append((relative, rule))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-tracked", action="store_true", help="scan all tracked files")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        repo = Path(git_lines(args.repo_root, ["rev-parse", "--show-toplevel"])[0])
        findings = check_files(repo, target_files(repo, args.all_tracked))
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        return 2
    if findings:
        for path, rule in findings:
            print(f"FAIL: {path} — {rule}")
        return 2
    scope = "all tracked files" if args.all_tracked else "staged files"
    print(f"PASS: no public-boundary risks found in {scope}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
