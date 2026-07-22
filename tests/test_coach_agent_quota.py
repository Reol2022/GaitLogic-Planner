from datetime import datetime, timedelta, timezone

import pytest

from server.common.exceptions import TooManyRequestsError
from server.services.coach_agent_usage_service import CoachAgentRateLimiter, CoachAgentUsageRecorder
from server.agent.providers.schemas import AgentProviderUsage


def test_rate_limiter_enforces_cooldown_per_user() -> None:
    now = datetime(2026, 7, 22, tzinfo=timezone.utc)
    limiter = CoachAgentRateLimiter(daily_limit=5, cooldown_seconds=10, clock=lambda: now)
    limiter.check_and_consume(1)
    with pytest.raises(TooManyRequestsError):
        limiter.check_and_consume(1)
    limiter.check_and_consume(2)


def test_rate_limiter_enforces_rolling_daily_limit() -> None:
    values = iter(
        [
            datetime(2026, 7, 22, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 7, 22, 0, 1, tzinfo=timezone.utc),
            datetime(2026, 7, 22, 0, 2, tzinfo=timezone.utc),
        ]
    )
    limiter = CoachAgentRateLimiter(daily_limit=2, cooldown_seconds=0, clock=lambda: next(values))
    limiter.check_and_consume(1)
    limiter.check_and_consume(1)
    with pytest.raises(TooManyRequestsError):
        limiter.check_and_consume(1)


def test_usage_record_contains_no_prompt_context_or_answer() -> None:
    record = CoachAgentUsageRecorder().record(
        provider="fictional",
        model="fictional-model",
        usage=AgentProviderUsage(prompt_tokens=12, completion_tokens=4, status="SUCCEEDED"),
        status="SUCCEEDED",
    )
    assert set(record.__dict__) == {
        "capability", "provider", "model", "status", "prompt_tokens",
        "completion_tokens", "duration_ms", "safe_error_code",
    }
