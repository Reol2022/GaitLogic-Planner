"""Thin MCP adapters over the existing request-scoped Coach tool registry."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.orm import Session

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.schemas import AgentContext
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.mcp.context import McpExecutionContext
from server.mcp.errors import McpErrorCode, McpSafeError
from server.mcp.schemas import (
    McpDataQuality,
    McpError,
    McpEvidence,
    McpNotice,
    McpRecentTraining,
    McpRecentTrainingItem,
    McpRecentTrainingResult,
    McpRecentTrainingSummary,
    McpRunnerState,
    McpRunnerStateResult,
    McpTodayPlan,
    McpTodayPlanResult,
)
from server.services.weekly_review_stats_service import APP_TIMEZONE


logger = logging.getLogger(__name__)
DependenciesFactory = Callable[[Session], CoachAgentToolDependencies]


_ERROR_MESSAGES = {
    McpErrorCode.INVALID_ARGUMENT: "The tool arguments are invalid.",
    McpErrorCode.AUTH_CONTEXT_MISSING: "An authenticated execution context is required.",
    McpErrorCode.RESOURCE_NOT_FOUND: "The requested training resource was not found.",
    McpErrorCode.DATA_UNAVAILABLE: "The requested training data is currently unavailable.",
    McpErrorCode.SERVICE_FAILURE: "The training data service could not complete this request.",
    McpErrorCode.INTERNAL_SAFE_ERROR: "The server could not safely complete this request.",
}


class McpToolAdapter:
    """Maps the three public MCP tools to existing Coach read-only tools.

    This adapter has no SQL of its own.  It creates the same request-scoped
    dependencies and registry used by Coach Agent calls, injects only trusted
    server-side identity, then maps bounded canonical output into MCP public
    schemas.  Every opened Session is rolled back and closed as an additional
    read-only guard.
    """

    def __init__(
        self,
        execution_context: McpExecutionContext,
        *,
        dependencies_factory: DependenciesFactory = CoachAgentToolDependencies.from_session,
    ) -> None:
        self.execution_context = execution_context
        self._dependencies_factory = dependencies_factory

    @staticmethod
    def _notice(value: dict) -> McpNotice:
        return McpNotice.model_validate(value)

    @classmethod
    def _today_plan(cls, value: dict) -> McpTodayPlan:
        return McpTodayPlan(
            data_status=value["data_status"],
            workout_status=value["workout_status"],
            date=value["date"],
            training_type=value.get("training_type"),
            title=value.get("title"),
            distance_or_duration_target=value.get("distance_or_duration_target"),
            pace_target=value.get("pace_target"),
            completion_status=value.get("completion_status"),
            limitations=[cls._notice(item) for item in value.get("limitations", [])],
        )

    @classmethod
    def _recent_training(cls, value: dict) -> McpRecentTraining:
        return McpRecentTraining(
            data_status=value["data_status"],
            as_of=value["as_of"],
            # Do not map ``brief_review``: it is free-text training-log content.
            items=[
                McpRecentTrainingItem.model_validate(
                    {key: item.get(key) for key in McpRecentTrainingItem.model_fields}
                )
                for item in value.get("items", [])
            ],
            summary=McpRecentTrainingSummary.model_validate(value["summary"]),
            data_quality=McpDataQuality.model_validate(value["data_quality"]),
            missing_reasons=value.get("missing_reasons", []),
        )

    @classmethod
    def _runner_state(cls, value: dict) -> McpRunnerState:
        return McpRunnerState(
            data_status=value["data_status"],
            as_of_date=value["as_of_date"],
            overall_state=value["overall_state"],
            risk_level=value["risk_level"],
            data_quality=McpDataQuality.model_validate(value["data_quality"]),
            metrics=value["metrics"],
            evidence=[McpEvidence.model_validate(item) for item in value.get("evidence", [])],
            warnings=[cls._notice(item) for item in value.get("warnings", [])],
            limitations=[cls._notice(item) for item in value.get("limitations", [])],
        )

    @staticmethod
    def _error(code: McpErrorCode) -> McpError:
        return McpError(code=code, message=_ERROR_MESSAGES[code])

    @staticmethod
    def _map_registry_failure(status: AgentToolStatus) -> McpErrorCode:
        return {
            AgentToolStatus.INVALID_ARGUMENTS: McpErrorCode.INVALID_ARGUMENT,
            AgentToolStatus.NOT_FOUND: McpErrorCode.RESOURCE_NOT_FOUND,
            AgentToolStatus.NOT_ALLOWED: McpErrorCode.DATA_UNAVAILABLE,
            AgentToolStatus.FAILED: McpErrorCode.SERVICE_FAILURE,
        }.get(status, McpErrorCode.INTERNAL_SAFE_ERROR)

    def _agent_context(self, user_id: int) -> AgentContext:
        now = datetime.now(ZoneInfo(APP_TIMEZONE.key))
        return AgentContext(
            request_id=uuid4(),
            user_id=user_id,
            intent=AgentIntent.GENERAL_TRAINING_QUESTION,
            current_time=now,
            timezone=APP_TIMEZONE.key,
        )

    def _invoke(self, *, mcp_tool_name: str, agent_tool_name: str, arguments: dict) -> tuple[dict | None, McpErrorCode | None]:
        identity = self.execution_context.identity_provider()
        if identity is None:
            return None, McpErrorCode.AUTH_CONTEXT_MISSING
        if self.execution_context.session_factory is None:
            return None, McpErrorCode.AUTH_CONTEXT_MISSING

        session: Session | None = None
        failure: McpErrorCode | None = None
        tracer = self.execution_context.tracer
        metadata = {
            "transport": self.execution_context.transport,
            "tool_name": mcp_tool_name,
            "operation_type": "mcp_tool",
        }
        try:
            with tracer.request(component="mcp", operation="request", metadata=metadata) as handle:
                with tracer.span(handle, component="mcp", operation="tool", metadata=metadata) as span:
                    session = self.execution_context.session_factory()
                    registry = build_coach_agent_tool_registry(self._dependencies_factory(session))
                    result = registry.invoke(
                        agent_tool_name,
                        arguments,
                        self._agent_context(identity.user_id),
                    )
                    if result.status != AgentToolStatus.SUCCEEDED:
                        failure = self._map_registry_failure(result.status)
                        span.set_status("FAILED", error_code=failure.value)
                        span.add_metadata(status="FAILED", failure_category=failure.value)
                        return None, failure
                    span.add_metadata(status="SUCCEEDED")
                    return result.data if isinstance(result.data, dict) else None, None
        except McpSafeError as exc:
            failure = exc.code
        except Exception:
            failure = McpErrorCode.SERVICE_FAILURE
            logger.warning(
                "mcp_tool_service_failed code=MCP_TOOL_SERVICE_FAILURE tool_name=%s",
                mcp_tool_name,
            )
        finally:
            if session is not None:
                try:
                    # Query-only tools must never leave uncommitted work behind.
                    session.rollback()
                except Exception:
                    logger.warning("mcp_session_rollback_failed code=MCP_SESSION_ROLLBACK_FAILED")
                finally:
                    session.close()
        return None, failure or McpErrorCode.INTERNAL_SAFE_ERROR

    def get_today_plan(self) -> McpTodayPlanResult:
        payload, error = self._invoke(
            mcp_tool_name="get_today_plan", agent_tool_name="get_today_workout", arguments={}
        )
        if error is not None:
            return McpTodayPlanResult(status="FAILED", error=self._error(error))
        try:
            return McpTodayPlanResult(status="SUCCEEDED", data=self._today_plan(payload or {}))
        except (KeyError, ValidationError):
            return McpTodayPlanResult(
                status="FAILED", error=self._error(McpErrorCode.INTERNAL_SAFE_ERROR)
            )

    def get_recent_training(self, *, days: int = 7, limit: int = 20) -> McpRecentTrainingResult:
        payload, error = self._invoke(
            mcp_tool_name="get_recent_training",
            agent_tool_name="get_recent_training",
            arguments={"days": days, "limit": limit},
        )
        if error is not None:
            return McpRecentTrainingResult(status="FAILED", error=self._error(error))
        try:
            return McpRecentTrainingResult(
                status="SUCCEEDED", data=self._recent_training(payload or {})
            )
        except (KeyError, ValidationError):
            return McpRecentTrainingResult(
                status="FAILED", error=self._error(McpErrorCode.INTERNAL_SAFE_ERROR)
            )

    def get_runner_state(self) -> McpRunnerStateResult:
        payload, error = self._invoke(
            mcp_tool_name="get_runner_state", agent_tool_name="get_runner_state", arguments={}
        )
        if error is not None:
            return McpRunnerStateResult(status="FAILED", error=self._error(error))
        try:
            return McpRunnerStateResult(status="SUCCEEDED", data=self._runner_state(payload or {}))
        except (KeyError, ValidationError):
            return McpRunnerStateResult(
                status="FAILED", error=self._error(McpErrorCode.INTERNAL_SAFE_ERROR)
            )
