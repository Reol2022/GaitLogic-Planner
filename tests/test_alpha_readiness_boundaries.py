from __future__ import annotations

from pathlib import Path
import re

from server.schemas.coach_agent import CoachQueryResponse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ALPHA_DOCS = tuple((REPOSITORY_ROOT / "docs/alpha").glob("*.md"))


def test_alpha_document_set_is_complete_and_contains_no_private_paths() -> None:
    expected = {
        "gaitlogic-v0120-alpha-onboarding.md",
        "gaitlogic-v0120-alpha-test-plan.md",
        "gaitlogic-v0120-alpha-feedback-guide.md",
        "gaitlogic-v0120-alpha-privacy-and-limits.md",
        "gaitlogic-v0120-alpha-incident-runbook.md",
    }
    assert {item.name for item in ALPHA_DOCS} == expected
    combined = "\n".join(
        item.read_text(encoding="utf-8") for item in ALPHA_DOCS
    )
    assert not re.search(r"(?i)[A-Z]:\\", combined)
    assert not re.search(
        r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        combined,
    )
    assert not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", combined)
    assert "BEGIN PRIVATE KEY" not in combined


def test_public_coach_schema_does_not_expose_internal_reference_ids() -> None:
    schema = CoachQueryResponse.model_json_schema()
    serialized = str(schema)
    assert "knowledge_reference_ids" not in serialized
    assert "chunk_id" not in serialized
    assert "relative_path" not in serialized
    assert "score" not in serialized


def test_readiness_and_smoke_source_do_not_log_sensitive_payloads() -> None:
    readiness = (
        REPOSITORY_ROOT / "scripts/check_coach_rag_readiness.py"
    ).read_text(encoding="utf-8")
    smoke = (
        REPOSITORY_ROOT / "scripts/smoke_coach_rag.py"
    ).read_text(encoding="utf-8")
    assert "coach_agent_api_key" not in readiness
    assert "knowledge_embedding_api_key" not in readiness
    assert "user_message" not in smoke
    assert "tool_results" not in smoke
    assert "reasoning_content" in smoke  # Explicitly documented as omitted.
