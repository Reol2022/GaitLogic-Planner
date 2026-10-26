"""Cross-layer, privacy-safe Coach failure attribution.

Provider transport categories and validator error codes intentionally remain the
source of truth.  This module only maps them to a small stable vocabulary for
traces and aggregate evaluation; it never stores provider text, prompts,
reasoning, or training facts.
"""

from __future__ import annotations

from enum import Enum

from server.provider_reliability import ProviderFailureCategory


class CoachFailureCategory(str, Enum):
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
    OUTPUT_PARSE_FAILED = "OUTPUT_PARSE_FAILED"
    OUTPUT_SCHEMA_INVALID = "OUTPUT_SCHEMA_INVALID"
    EVIDENCE_UNSUPPORTED = "EVIDENCE_UNSUPPORTED"
    FACT_CONFLICT = "FACT_CONFLICT"
    CAPABILITY_BOUNDARY = "CAPABILITY_BOUNDARY"
    SAFETY_BOUNDARY = "SAFETY_BOUNDARY"
    PLAN_RULE_VIOLATION = "PLAN_RULE_VIOLATION"


def provider_failure_category(category: ProviderFailureCategory) -> CoachFailureCategory:
    """Map a provider-neutral error to the public aggregate taxonomy."""

    if category == ProviderFailureCategory.PROVIDER_TIMEOUT:
        return CoachFailureCategory.PROVIDER_TIMEOUT
    if category == ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED:
        return CoachFailureCategory.OUTPUT_TRUNCATED
    if category in {
        ProviderFailureCategory.PROVIDER_INVALID_RESPONSE,
        ProviderFailureCategory.PROVIDER_EMPTY_CONTENT,
        ProviderFailureCategory.PROVIDER_INVALID_JSON,
    }:
        return CoachFailureCategory.OUTPUT_PARSE_FAILED
    if category in {
        ProviderFailureCategory.PROVIDER_SCHEMA_ERROR,
        ProviderFailureCategory.PROVIDER_TOOL_PROTOCOL_ERROR,
    }:
        return CoachFailureCategory.OUTPUT_SCHEMA_INVALID
    return CoachFailureCategory.PROVIDER_ERROR
