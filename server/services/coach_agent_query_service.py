from __future__ import annotations

from datetime import datetime
import logging
from functools import lru_cache

from sqlalchemy.orm import Session

from planner_core.config import Settings, get_settings
from server.agent.enums import AgentIntent, AgentRiskLevel, AgentRunStatus, AgentToolStatus
from server.agent.errors import AgentErrorCode
from server.agent.fallback import DeterministicCoachFallback
from server.agent.gateway import AgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.providers.errors import AgentProviderError
from server.agent.providers.openai_compatible import OpenAICompatibleAgentGateway
from server.agent.providers.schemas import AgentProviderUsage
from server.agent.schemas import AgentLimits, AgentNotice, AgentRequest
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.agent.training_context_builder import AgentTrainingContextBuilder
from server.agent.trace import AgentTrace
from server.schemas.coach_agent import CoachQueryRequest, CoachQueryResponse, CoachToolCallRead
from server.services.coach_agent_usage_service import (
    CoachAgentRateLimiter,
    CoachAgentUsageRecorder,
)
from server.services.weekly_review_stats_service import APP_TIMEZONE

_PUBLIC_INTENTS = {
    AgentIntent.TODAY_RECOMMENDATION,
    AgentIntent.EXPLAIN_RUNNER_STATE,
    AgentIntent.GENERAL_TRAINING_QUESTION,
}

logger = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def _shared_rate_limiter(daily_limit: int, cooldown_seconds: int) -> CoachAgentRateLimiter:
    return CoachAgentRateLimiter(
        daily_limit=daily_limit,
        cooldown_seconds=cooldown_seconds,
    )


class _UnavailableGateway(AgentLLMGateway):
    def __init__(self, code: AgentErrorCode) -> None:
        self.code = code
        self.last_usage = AgentProviderUsage(status="NOT_CALLED", safe_error_code=code.value)

    def generate(self, **_kwargs):
        raise AgentProviderError(self.code)


class CoachAgentQueryService:
    """Request-scoped composition boundary for public Coach queries."""

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        gateway: AgentLLMGateway | None = None,
        rate_limiter: CoachAgentRateLimiter | None = None,
        usage_recorder: CoachAgentUsageRecorder | None = None,
        clock=None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.gateway_override = gateway
        self.rate_limiter = rate_limiter or _shared_rate_limiter(
            self.settings.coach_agent_daily_limit,
            self.settings.coach_agent_cooldown_seconds,
        )
        self.usage_recorder = usage_recorder or CoachAgentUsageRecorder()
        self.clock = clock or (lambda: datetime.now(APP_TIMEZONE))

    @staticmethod
    def _infer_intent(message: str) -> AgentIntent:
        lowered = message.lower()
        if any(marker in lowered for marker in ("today", "今天", "今日", "跑什么", "该不该跑")):
            return AgentIntent.TODAY_RECOMMENDATION
        if any(marker in lowered for marker in ("runner state", "training state", "跑者状态", "训练状态")):
            return AgentIntent.EXPLAIN_RUNNER_STATE
        return AgentIntent.GENERAL_TRAINING_QUESTION

    def _limits(self) -> AgentLimits:
        return AgentLimits(
            max_model_calls=self.settings.agent_max_model_calls,
            max_tool_calls=self.settings.agent_max_tool_calls,
            max_same_tool_calls=self.settings.agent_max_same_tool_calls,
            max_message_length=self.settings.agent_max_message_length,
            max_context_items=self.settings.agent_max_context_items,
            max_context_chars=self.settings.agent_max_context_chars,
            max_recent_training_items=self.settings.agent_max_recent_training_items,
            max_history_items=self.settings.agent_max_history_items,
            max_evidence_items=self.settings.agent_max_evidence_items,
            max_rule_items=self.settings.agent_max_rule_items,
            max_answer_length=self.settings.agent_max_answer_length,
        )

    def _gateway(self) -> tuple[AgentLLMGateway, str]:
        if self.gateway_override is not None:
            return self.gateway_override, "SUCCEEDED"
        if not self.settings.coach_agent_enabled:
            return _UnavailableGateway(AgentErrorCode.AGENT_PROVIDER_DISABLED), "DISABLED"
        if not self.settings.coach_agent_api_key:
            return _UnavailableGateway(AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED), "UNCONFIGURED"
        return OpenAICompatibleAgentGateway(self.settings), "SUCCEEDED"

    def _rejected(
        self,
        request: AgentRequest,
        intent: AgentIntent,
    ) -> CoachQueryResponse:
        trace = AgentTrace(request_id=request.request_id)
        return CoachQueryResponse(
            request_id=request.request_id,
            trace_id=trace.trace_id,
            status="REJECTED",
            intent=intent,
            answer=None,
            summary=None,
            risk_level=AgentRiskLevel.UNKNOWN,
            warnings=[],
            limitations=[
                AgentNotice(
                    code=AgentErrorCode.AGENT_UNSUPPORTED_INTENT.value,
                    message="This Coach intent is not available in the current release.",
                )
            ],
            provider_status="NOT_CALLED",
            generated_at=self.clock(),
        )

    def query(self, *, user_id: int, payload: CoachQueryRequest) -> CoachQueryResponse:
        intent = payload.intent or self._infer_intent(payload.message)
        request = AgentRequest.for_authenticated_user(
            user_id=user_id,
            message=payload.message,
            intent=intent,
            conversation_context=payload.conversation_context,
        )
        if intent not in _PUBLIC_INTENTS:
            return self._rejected(request, intent)

        self.rate_limiter.check_and_consume(user_id)
        limits = self._limits()
        dependencies = CoachAgentToolDependencies.from_session(self.db)
        registry = build_coach_agent_tool_registry(dependencies, limits=limits)
        context_builder = AgentTrainingContextBuilder(registry=registry, limits=limits)
        gateway, initial_provider_status = self._gateway()
        agent = GaitLogicCoachAgent(
            gateway=gateway,
            registry=registry,
            context_builder=context_builder,
            limits=limits,
        )
        try:
            agent_response = agent.run(request)
        finally:
            if self.gateway_override is None and isinstance(
                gateway, OpenAICompatibleAgentGateway
            ):
                try:
                    gateway.close()
                except Exception:
                    logger.warning("coach_provider_client_close_failed")
        context = agent.last_context
        usage = getattr(gateway, "last_usage", AgentProviderUsage())
        provider_status = initial_provider_status
        if initial_provider_status == "SUCCEEDED":
            provider_status = "SUCCEEDED" if agent_response.status == AgentRunStatus.SUCCEEDED else "FAILED"
        try:
            self.usage_recorder.record(
                provider=self.settings.coach_agent_provider,
                model=self.settings.coach_agent_model,
                usage=usage,
                status=provider_status,
            )
        except Exception:
            logger.warning("coach_agent_usage_record_failed status=%s", provider_status)

        tool_calls = [
            CoachToolCallRead(
                tool_name=item.tool_name,
                status=item.status,
                safe_error_code=item.safe_error_code,
            )
            for item in agent_response.tool_calls
        ]
        context_has_tool_failure = context is not None and any(
            item.status != AgentToolStatus.SUCCEEDED for item in context.tool_results
        )
        if agent_response.status == AgentRunStatus.SUCCEEDED and not context_has_tool_failure:
            return CoachQueryResponse(
                request_id=agent_response.request_id,
                trace_id=agent_response.trace_id,
                status="SUCCEEDED",
                intent=agent_response.intent,
                answer=agent_response.answer,
                summary=agent_response.summary,
                risk_level=agent_response.risk_level,
                today_recommendation=agent_response.today_recommendation,
                tool_calls=tool_calls,
                warnings=agent_response.warnings,
                limitations=agent_response.limitations,
                provider_status=provider_status,
                generated_at=self.clock(),
            )

        if context is None:
            return CoachQueryResponse(
                request_id=agent_response.request_id,
                trace_id=agent_response.trace_id,
                status="UNAVAILABLE",
                intent=intent,
                risk_level=AgentRiskLevel.UNKNOWN,
                tool_calls=tool_calls,
                limitations=[
                    AgentNotice(
                        code=AgentErrorCode.AGENT_INTERNAL_ERROR.value,
                        message="Coach context could not be built safely.",
                    )
                ],
                provider_status=provider_status,
                generated_at=self.clock(),
            )

        fallback = DeterministicCoachFallback().build(
            intent=intent,
            message=payload.message,
            context=context,
            trace=agent.last_trace,
        )
        return CoachQueryResponse(
            request_id=agent_response.request_id,
            trace_id=agent_response.trace_id,
            status="DEGRADED",
            intent=intent,
            answer=fallback.answer,
            summary=fallback.summary,
            risk_level=fallback.risk_level,
            today_recommendation=fallback.today_recommendation,
            tool_calls=tool_calls,
            warnings=fallback.warnings,
            limitations=fallback.limitations,
            provider_status=provider_status,
            generated_at=self.clock(),
        )
