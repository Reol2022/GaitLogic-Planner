from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Callable

from server.agent.providers.schemas import AgentProviderUsage
from server.common.exceptions import TooManyRequestsError

logger = logging.getLogger(__name__)


class CoachAgentRateLimiter:
    """Process-local protection; no prompt or training data is retained."""

    def __init__(
        self,
        *,
        daily_limit: int,
        cooldown_seconds: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.daily_limit = daily_limit
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._calls: dict[int, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    def check_and_consume(self, user_id: int) -> None:
        now = self.clock()
        cutoff = now - timedelta(days=1)
        with self._lock:
            calls = self._calls[user_id]
            while calls and calls[0] < cutoff:
                calls.popleft()
            if len(calls) >= self.daily_limit:
                raise TooManyRequestsError("Coach Agent daily request limit reached.")
            if calls and now - calls[-1] < self.cooldown:
                raise TooManyRequestsError("Coach Agent requests are too frequent.")
            calls.append(now)


@dataclass(frozen=True)
class CoachAgentUsageRecord:
    capability: str
    provider: str
    model: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    duration_ms: float | None
    safe_error_code: str | None


class CoachAgentUsageRecorder:
    """Safe operational usage logger; intentionally stores no request content."""

    def record(
        self,
        *,
        provider: str,
        model: str,
        usage: AgentProviderUsage,
        status: str,
    ) -> CoachAgentUsageRecord:
        record = CoachAgentUsageRecord(
            capability="coach_agent_query",
            provider=provider,
            model=model,
            status=status,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            duration_ms=usage.duration_ms,
            safe_error_code=usage.safe_error_code,
        )
        logger.info(
            "coach_agent_usage capability=%s provider=%s model=%s status=%s prompt_tokens=%s completion_tokens=%s duration_ms=%s error=%s",
            record.capability,
            record.provider,
            record.model,
            record.status,
            record.prompt_tokens,
            record.completion_tokens,
            record.duration_ms,
            record.safe_error_code,
        )
        return record
