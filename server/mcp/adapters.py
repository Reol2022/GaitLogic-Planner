"""Thin MCP adapters over the existing request-scoped Coach tool registry."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from uuid import uuid4
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from sqlalchemy.orm import Session

from planner_core.config import get_settings
from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.knowledge_references import materialize_knowledge_references
from server.agent.schemas import AgentContext, AgentToolResult
from server.agent.tools.knowledge_tools import (
    RetrieveTrainingKnowledgeInput,
    RetrieveTrainingKnowledgeTool,
    build_configured_knowledge_tool,
)
from server.agent.tools.dependencies import CoachAgentToolDependencies
from server.agent.tools.factory import build_coach_agent_tool_registry
from server.mcp.context import McpExecutionContext
from server.mcp.errors import McpErrorCode, McpSafeError
from server.mcp.schemas import (
    McpDataQuality,
    McpError,
    McpEvidence,
    McpKnowledgeReference,
    McpKnowledgeRetrieval,
    McpKnowledgeRetrievalResult,
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
from server.knowledge_retrieval.errors import KnowledgeCorpusError
from server.observability.tracing import active_trace_handle, active_tracer
from server.services.weekly_review_stats_service import APP_TIMEZONE


logger = logging.getLogger(__name__)
DependenciesFactory = Callable[[Session], CoachAgentToolDependencies]
KnowledgeToolFactory = Callable[[], RetrieveTrainingKnowledgeTool | None]


_ERROR_MESSAGES = {
    McpErrorCode.INVALID_ARGUMENT: "The tool arguments are invalid.",
    McpErrorCode.AUTH_CONTEXT_MISSING: "An authenticated execution context is required.",
    McpErrorCode.RESOURCE_NOT_FOUND: "The requested training resource was not found.",
    McpErrorCode.SERVICE_FAILURE: "The training data service could not complete this request.",
    McpErrorCode.INTERNAL_SAFE_ERROR: "The server could not safely complete this request.",
    McpErrorCode.DATA_UNAVAILABLE: "The requested training data is currently unavailable.",
}


class McpToolAdapter:
    """Maps four public MCP tools to existing read-only application services.

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
        knowledge_tool_factory: KnowledgeToolFactory | None = None,
    ) -> None:
        self.execution_context = execution_context
        self._dependencies_factory = dependencies_factory
        self._knowledge_tool_factory = knowledge_tool_factory or (
            lambda: build_configured_knowledge_tool(get_settings())
        )

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

    def _canonical_knowledge(
        self,
        output,
        context: AgentContext,
    ) -> McpKnowledgeRetrieval:
        context.tool_results = [
            AgentToolResult(
                tool_call_id=uuid4(),
                tool_name="retrieve_training_knowledge",
                status=AgentToolStatus.SUCCEEDED,
                data=output.model_dump(mode="json"),
            )
        ]
        public = materialize_knowledge_references(
            [item.knowledge_reference_id for item in output.results], context
        )
        return McpKnowledgeRetrieval(
            query_status=output.query_status,
            references=[
                McpKnowledgeReference(
                    reference_id=internal.knowledge_reference_id,
                    document_id=reference.document_id,
                    title=reference.title,
                    section=reference.section,
                    source=reference.source_title,
                    version=reference.knowledge_version,
                    evidence_level=reference.evidence_level,
                    excerpt=reference.excerpt,
                    limitations=reference.limitations,
                )
                for internal, reference in zip(output.results, public, strict=True)
            ],
            limitations=output.limitations,
        )

    def retrieve_training_knowledge(
        self,
        *,
        query: str,
        top_k: int = 4,
        categories: list[str] | None = None,
        tags: list[str] | None = None,
        language: str = "zh-CN",
    ) -> McpKnowledgeRetrievalResult:
        identity = self.execution_context.identity_provider()
        if identity is None:
            return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.AUTH_CONTEXT_MISSING))

        metadata = {
            "transport": self.execution_context.transport,
            "tool_name": "retrieve_training_knowledge",
            "operation_type": "mcp_tool",
        }

        def execute() -> McpKnowledgeRetrievalResult:
            return self._retrieve_training_knowledge(
                identity.user_id,
                query=query,
                top_k=top_k,
                categories=categories,
                tags=tags,
                language=language,
            )

        tracer = self.execution_context.tracer
        active_handle = active_trace_handle()
        inherited_tracer = active_tracer()
        if active_handle is not None and inherited_tracer is tracer:
            return self._run_knowledge_with_trace(tracer, active_handle, metadata, execute)
        with tracer.request(component="mcp", operation="request", metadata=metadata) as handle:
            return self._run_knowledge_with_trace(tracer, handle, metadata, execute)

    def _run_knowledge_with_trace(self, tracer, handle, metadata: dict, execute) -> McpKnowledgeRetrievalResult:
        with tracer.span(handle, component="mcp", operation="tool", metadata=metadata) as span:
            result = execute()
            if result.status == "FAILED":
                error_code = result.error.code.value if result.error is not None else McpErrorCode.INTERNAL_SAFE_ERROR.value
                span.set_status("FAILED", error_code=error_code)
                span.add_metadata(status="FAILED", failure_category=error_code)
            else:
                span.add_metadata(
                    status="SUCCEEDED",
                    result_count=len(result.data.references) if result.data is not None else 0,
                )
            return result

    def _retrieve_training_knowledge(
        self,
        user_id: int,
        *,
        query: str,
        top_k: int,
        categories: list[str] | None,
        tags: list[str] | None,
        language: str,
    ) -> McpKnowledgeRetrievalResult:
        try:
            arguments = RetrieveTrainingKnowledgeInput.model_validate(
                {
                    "query": query,
                    "top_k": top_k,
                    "categories": categories or [],
                    "tags": tags or [],
                    "language": language,
                }
            )
            tool = self._knowledge_tool_factory()
            if tool is None:
                return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.DATA_UNAVAILABLE))
            context = self._agent_context(user_id)
            output = tool.execute(arguments, context)
            return McpKnowledgeRetrievalResult(
                status="SUCCEEDED", data=self._canonical_knowledge(output, context)
            )
        except ValidationError:
            return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.INVALID_ARGUMENT))
        except KnowledgeCorpusError:
            return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.DATA_UNAVAILABLE))
        except ValueError:
            return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.SERVICE_FAILURE))
        except Exception:
            logger.warning("mcp_knowledge_tool_failed code=MCP_KNOWLEDGE_TOOL_FAILED")
            return McpKnowledgeRetrievalResult(status="FAILED", error=self._error(McpErrorCode.SERVICE_FAILURE))

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
            active_handle = active_trace_handle()
            inherited_tracer = active_tracer()
            if active_handle is not None and inherited_tracer is tracer:
                return self._invoke_with_trace(
                    tracer, active_handle, mcp_tool_name, agent_tool_name, arguments, identity.user_id, metadata
                )
            with tracer.request(component="mcp", operation="request", metadata=metadata) as handle:
                return self._invoke_with_trace(
                    tracer, handle, mcp_tool_name, agent_tool_name, arguments, identity.user_id, metadata
                )
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

    def _invoke_with_trace(
        self,
        tracer,
        handle,
        mcp_tool_name: str,
        agent_tool_name: str,
        arguments: dict,
        user_id: int,
        metadata: dict,
    ) -> tuple[dict | None, McpErrorCode | None]:
        session: Session | None = None
        try:
                with tracer.span(handle, component="mcp", operation="tool", metadata=metadata) as span:
                    session = self.execution_context.session_factory()
                    registry = build_coach_agent_tool_registry(self._dependencies_factory(session))
                    result = registry.invoke(
                        agent_tool_name,
                        arguments,
                        self._agent_context(user_id),
                    )
                    if result.status != AgentToolStatus.SUCCEEDED:
                        failure = self._map_registry_failure(result.status)
                        span.set_status("FAILED", error_code=failure.value)
                        span.add_metadata(status="FAILED", failure_category=failure.value)
                        return None, failure
                    span.add_metadata(status="SUCCEEDED")
                    return result.data if isinstance(result.data, dict) else None, None
        finally:
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    logger.warning("mcp_session_rollback_failed code=MCP_SESSION_ROLLBACK_FAILED")
                finally:
                    session.close()

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
