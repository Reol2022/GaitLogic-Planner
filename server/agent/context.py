from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pydantic import BaseModel, JsonValue, TypeAdapter, ValidationError

from server.agent.schemas import (
    AgentContext,
    AgentContextSeed,
    AgentLimits,
    AgentRequest,
    MAX_CONTEXT_JSON_CHARS,
)

DEFAULT_AGENT_TIMEZONE = "Asia/Shanghai"
_JSON_MAPPING_ADAPTER = TypeAdapter(dict[str, JsonValue])


class AgentContextBuilder:
    """Builds bounded, JSON-only context without querying a database."""

    def __init__(
        self,
        *,
        timezone_name: str = DEFAULT_AGENT_TIMEZONE,
        clock: Callable[[], datetime] | None = None,
        limits: AgentLimits | None = None,
    ) -> None:
        self.timezone_name = timezone_name
        self.timezone = ZoneInfo(timezone_name)
        self.clock = clock or (lambda: datetime.now(self.timezone))
        self.limits = limits or AgentLimits()

    @staticmethod
    def _safe_mapping(value: BaseModel | Mapping[str, Any] | None) -> dict[str, JsonValue] | None:
        if value is None:
            return None
        raw: Any = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
        try:
            result = _JSON_MAPPING_ADAPTER.validate_python(raw)
        except ValidationError as exc:
            raise ValueError("agent context data must be JSON-compatible") from exc
        serialized = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False)
        if len(serialized) > MAX_CONTEXT_JSON_CHARS:
            raise ValueError("agent context field is too large")
        return result

    def create_seed(
        self,
        *,
        runner_state: BaseModel | Mapping[str, Any] | None = None,
        recent_training: BaseModel | Mapping[str, Any] | None = None,
        today_workout: BaseModel | Mapping[str, Any] | None = None,
        current_cycle: BaseModel | Mapping[str, Any] | None = None,
        applicable_rules: list[BaseModel | Mapping[str, Any]] | None = None,
        data_quality: BaseModel | Mapping[str, Any] | None = None,
        missing_reasons: Mapping[str, str] | None = None,
    ) -> AgentContextSeed:
        rules = [self._safe_mapping(item) or {} for item in (applicable_rules or [])]
        if len(rules) > self.limits.max_context_items:
            raise ValueError("too many applicable rules")
        return AgentContextSeed(
            runner_state=self._safe_mapping(runner_state),
            recent_training=self._safe_mapping(recent_training),
            today_workout=self._safe_mapping(today_workout),
            current_cycle=self._safe_mapping(current_cycle),
            applicable_rules=rules,
            data_quality=self._safe_mapping(data_quality),
            missing_reasons=dict(missing_reasons or {}),
        )

    def build(self, request: AgentRequest, seed: AgentContextSeed | None = None) -> AgentContext:
        seed = seed or AgentContextSeed()
        if len(seed.applicable_rules) > self.limits.max_context_items:
            raise ValueError("too many applicable rules")
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=self.timezone)
        return AgentContext(
            request_id=request.request_id,
            user_id=request.user_id,
            intent=request.intent,
            current_time=now.astimezone(self.timezone),
            timezone=self.timezone_name,
            conversation_context=request.conversation_context,
            runner_state=seed.runner_state,
            recent_training=seed.recent_training,
            today_workout=seed.today_workout,
            current_cycle=seed.current_cycle,
            applicable_rules=seed.applicable_rules,
            data_quality=seed.data_quality,
            missing_reasons=seed.missing_reasons,
        )
