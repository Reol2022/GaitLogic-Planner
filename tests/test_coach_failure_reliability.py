from __future__ import annotations

import pytest

from server.agent.reliability import CoachFailureCategory, provider_failure_category
from server.provider_reliability import ProviderFailureCategory


@pytest.mark.parametrize(
    ("provider_category", "expected"),
    [
        (ProviderFailureCategory.PROVIDER_TIMEOUT, CoachFailureCategory.PROVIDER_TIMEOUT),
        (ProviderFailureCategory.PROVIDER_OUTPUT_TRUNCATED, CoachFailureCategory.OUTPUT_TRUNCATED),
        (ProviderFailureCategory.PROVIDER_INVALID_JSON, CoachFailureCategory.OUTPUT_PARSE_FAILED),
        (ProviderFailureCategory.PROVIDER_EMPTY_CONTENT, CoachFailureCategory.OUTPUT_PARSE_FAILED),
        (ProviderFailureCategory.PROVIDER_SCHEMA_ERROR, CoachFailureCategory.OUTPUT_SCHEMA_INVALID),
        (ProviderFailureCategory.PROVIDER_TOOL_PROTOCOL_ERROR, CoachFailureCategory.OUTPUT_SCHEMA_INVALID),
        (ProviderFailureCategory.PROVIDER_RATE_LIMIT, CoachFailureCategory.PROVIDER_ERROR),
    ],
)
def test_provider_categories_are_aggregated_without_provider_details(
    provider_category: ProviderFailureCategory,
    expected: CoachFailureCategory,
) -> None:
    assert provider_failure_category(provider_category) == expected
