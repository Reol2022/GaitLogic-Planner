from __future__ import annotations

import logging
from collections import Counter
from time import perf_counter

from pydantic import ValidationError

from planner_core.config import get_settings
from server.agent.context import AgentContextBuilder
from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentRunStatus,
    AgentToolStatus,
    AgentTraceEventType,
    AgentTraceStatus,
)
from server.agent.errors import AgentErrorCode
from server.agent.gateway import AgentLLMGateway
from server.agent.knowledge_references import materialize_knowledge_references
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import (
    AgentContext,
    AgentContextSeed,
    AgentLimits,
    AgentModelOutput,
    AgentNotice,
    AgentRequest,
    AgentResponse,
    AgentToolCallSummary,
    AgentValidationResult,
)
from server.agent.trace import AgentTrace
from server.agent.validator import AgentResponseValidator
from server.agent.prompts import build_coach_agent_system_prompt

logger = logging.getLogger(__name__)

_ERROR_MESSAGES = {
    AgentErrorCode.AGENT_INVALID_REQUEST: "The agent request is invalid.",
    AgentErrorCode.AGENT_UNKNOWN_INTENT: "The request intent is not supported.",
    AgentErrorCode.AGENT_TOOL_NOT_FOUND: "A requested tool is unavailable.",
    AgentErrorCode.AGENT_TOOL_NOT_ALLOWED: "A requested action is not allowed.",
    AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID: "Tool arguments are invalid.",
    AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED: "A tool could not provide validated data.",
    AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID: "The model returned an invalid structured result.",
    AgentErrorCode.AGENT_MODEL_FAILED: "The model gateway could not complete the request.",
    AgentErrorCode.AGENT_VALIDATION_FAILED: "The response did not pass safety validation.",
    AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED: "The agent call limit was exceeded.",
    AgentErrorCode.AGENT_INTERNAL_ERROR: "The agent could not complete the request safely.",
}


class GaitLogicCoachAgent:
    """Bounded, provider-neutral Agent Core orchestration.

    The foundation is deliberately in-memory. It neither opens database
    sessions nor calls a provider directly; those responsibilities sit behind
    injected context and gateway boundaries.
    """

    def __init__(
        self,
        *,
        gateway: AgentLLMGateway,
        registry: AgentToolRegistry | None = None,
        context_builder: AgentContextBuilder | None = None,
        validator: AgentResponseValidator | None = None,
        limits: AgentLimits | None = None,
    ) -> None:
        self.limits = limits or self._limits_from_settings()
        self.gateway = gateway
        self.registry = registry or AgentToolRegistry()
        self.context_builder = context_builder or AgentContextBuilder(limits=self.limits)
        self.validator = validator or AgentResponseValidator(limits=self.limits)
        self.last_trace: AgentTrace | None = None
        self.last_context: AgentContext | None = None

    @staticmethod
    def _limits_from_settings() -> AgentLimits:
        settings = get_settings()
        return AgentLimits(
            max_model_calls=settings.agent_max_model_calls,
            max_tool_calls=settings.agent_max_tool_calls,
            max_same_tool_calls=settings.agent_max_same_tool_calls,
            max_message_length=settings.agent_max_message_length,
            max_context_items=settings.agent_max_context_items,
            max_context_chars=settings.agent_max_context_chars,
            max_recent_training_items=settings.agent_max_recent_training_items,
            max_history_items=settings.agent_max_history_items,
            max_evidence_items=settings.agent_max_evidence_items,
            max_rule_items=settings.agent_max_rule_items,
            max_answer_length=settings.agent_max_answer_length,
        )

    @staticmethod
    def _notice(code: AgentErrorCode) -> AgentNotice:
        return AgentNotice(code=code.value, message=_ERROR_MESSAGES[code])

    @staticmethod
    def _summaries(context: AgentContext | None) -> list[AgentToolCallSummary]:
        if context is None:
            return []
        return [
            AgentToolCallSummary(
                tool_call_id=result.tool_call_id,
                tool_name=result.tool_name,
                status=result.status,
                safe_error_code=result.safe_error_code,
            )
            for result in context.tool_results
        ]

    def _finish(
        self,
        *,
        request: AgentRequest,
        trace: AgentTrace,
        status: AgentRunStatus,
        context: AgentContext | None = None,
        output: AgentModelOutput | None = None,
        errors: list[AgentErrorCode] | None = None,
    ) -> AgentResponse:
        errors = list(dict.fromkeys(errors or []))
        knowledge_references = []
        if output is not None and context is not None:
            try:
                knowledge_references = materialize_knowledge_references(
                    output.knowledge_reference_ids,
                    context,
                )
            except ValueError:
                status = AgentRunStatus.VALIDATION_FAILED
                errors.append(AgentErrorCode.AGENT_VALIDATION_FAILED)
                output = None
                knowledge_references = []
        trace_status = (
            AgentTraceStatus.SUCCEEDED
            if status == AgentRunStatus.SUCCEEDED
            else AgentTraceStatus.REJECTED
            if status == AgentRunStatus.REJECTED
            else AgentTraceStatus.FAILED
        )
        trace.add_event(
            AgentTraceEventType.RUN_COMPLETED,
            trace_status,
            safe_error_code=errors[0] if errors else None,
        )
        self.last_trace = trace
        self.last_context = context
        logger.info(
            "coach_agent_run_complete request_id=%s trace_id=%s status=%s tool_calls=%s",
            request.request_id,
            trace.trace_id,
            status.value,
            len(context.tool_results) if context else 0,
        )

        limitations = list(output.limitations) if output else []
        existing_codes = {item.code for item in limitations}
        limitations.extend(
            self._notice(code) for code in errors if code.value not in existing_codes
        )
        return AgentResponse(
            request_id=request.request_id,
            status=status,
            intent=output.intent if output else request.intent,
            answer=output.answer if output else None,
            summary=output.summary if output else None,
            risk_level=output.risk_level if output else AgentRiskLevel.UNKNOWN,
            tool_calls=self._summaries(context),
            warnings=list(output.warnings) if output else [],
            limitations=limitations,
            knowledge_references=knowledge_references,
            trace_id=trace.trace_id,
            today_recommendation=output.today_recommendation if output else None,
        )

    def _call_model(
        self,
        *,
        request: AgentRequest,
        context: AgentContext,
        trace: AgentTrace,
    ) -> AgentModelOutput:
        started = perf_counter()
        trace.add_event(AgentTraceEventType.MODEL_CALL, AgentTraceStatus.STARTED)
        try:
            output = self.gateway.generate(
                system_instructions=build_coach_agent_system_prompt(),
                user_message=request.message,
                context=context,
                tools=self.registry.list_tools(request.intent),
                trace=trace,
            )
        except Exception:
            trace.add_event(
                AgentTraceEventType.MODEL_CALL,
                AgentTraceStatus.FAILED,
                safe_error_code=AgentErrorCode.AGENT_MODEL_FAILED,
                duration_ms=(perf_counter() - started) * 1000,
            )
            raise
        trace.add_event(
            AgentTraceEventType.MODEL_CALL,
            AgentTraceStatus.SUCCEEDED,
            duration_ms=(perf_counter() - started) * 1000,
        )
        return output

    def _validation_failure(
        self,
        *,
        request: AgentRequest,
        trace: AgentTrace,
        context: AgentContext | None,
        result: AgentValidationResult,
        output: AgentModelOutput | None = None,
    ) -> AgentResponse:
        errors = result.errors or [AgentErrorCode.AGENT_VALIDATION_FAILED]
        trace.add_event(
            AgentTraceEventType.RESPONSE_VALIDATED,
            AgentTraceStatus.FAILED,
            safe_error_code=errors[0],
        )
        return self._finish(
            request=request,
            trace=trace,
            status=AgentRunStatus.VALIDATION_FAILED,
            context=context,
            errors=errors,
        )

    def run(
        self,
        request: AgentRequest,
        *,
        context_seed: AgentContextSeed | None = None,
    ) -> AgentResponse:
        trace = AgentTrace(request_id=request.request_id)
        self.last_trace = trace
        request_validation = self.validator.validate_request(request)
        if not request_validation.valid:
            trace.add_event(
                AgentTraceEventType.REQUEST_VALIDATED,
                AgentTraceStatus.REJECTED,
                safe_error_code=request_validation.errors[0],
            )
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.REJECTED,
                errors=request_validation.errors,
            )
        trace.add_event(AgentTraceEventType.REQUEST_VALIDATED, AgentTraceStatus.SUCCEEDED)

        try:
            context = self.context_builder.build(request, context_seed, trace=trace)
        except Exception:
            trace.add_event(
                AgentTraceEventType.CONTEXT_BUILT,
                AgentTraceStatus.FAILED,
                safe_error_code=AgentErrorCode.AGENT_INVALID_REQUEST,
            )
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.REJECTED,
                errors=[AgentErrorCode.AGENT_INVALID_REQUEST],
            )
        trace.add_event(AgentTraceEventType.CONTEXT_BUILT, AgentTraceStatus.SUCCEEDED)

        try:
            first_output = self._call_model(request=request, context=context, trace=trace)
        except ValidationError:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.VALIDATION_FAILED,
                context=context,
                errors=[AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID],
            )
        except Exception:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.MODEL_FAILED,
                context=context,
                errors=[AgentErrorCode.AGENT_MODEL_FAILED],
            )

        first_validation = self.validator.validate_model_output(
            first_output,
            context=context,
            registry=self.registry,
            final=not first_output.tool_calls,
        )
        if not first_validation.valid:
            return self._validation_failure(
                request=request,
                trace=trace,
                context=context,
                result=first_validation,
                output=first_output,
            )
        trace.add_event(AgentTraceEventType.RESPONSE_VALIDATED, AgentTraceStatus.SUCCEEDED)
        if not first_output.tool_calls:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.SUCCEEDED,
                context=context,
                output=first_output,
            )

        repeated = Counter(call.tool_name for call in first_output.tool_calls)
        if (
            len(first_output.tool_calls) > self.limits.max_tool_calls
            or any(count > self.limits.max_same_tool_calls for count in repeated.values())
            or self.limits.max_model_calls < 2
        ):
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.REJECTED,
                context=context,
                errors=[AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED],
            )

        results = []
        for call in first_output.tool_calls:
            started = perf_counter()
            trace.add_event(
                AgentTraceEventType.TOOL_CALL,
                AgentTraceStatus.STARTED,
                tool_name=call.tool_name,
            )
            trace.add_event(
                AgentTraceEventType.MODEL_TOOL_STARTED,
                AgentTraceStatus.STARTED,
                tool_name=call.tool_name,
            )
            result = self.registry.invoke(
                call.tool_name,
                call.arguments,
                context,
                tool_call_id=call.tool_call_id,
            )
            results.append(result)
            trace.add_event(
                AgentTraceEventType.TOOL_CALL,
                AgentTraceStatus.SUCCEEDED
                if result.status == AgentToolStatus.SUCCEEDED
                else AgentTraceStatus.FAILED,
                tool_name=call.tool_name,
                safe_error_code=result.safe_error_code,
                duration_ms=(perf_counter() - started) * 1000,
            )
            trace.add_event(
                AgentTraceEventType.MODEL_TOOL_COMPLETED,
                AgentTraceStatus.SUCCEEDED
                if result.status == AgentToolStatus.SUCCEEDED
                else AgentTraceStatus.FAILED,
                tool_name=call.tool_name,
                safe_error_code=result.safe_error_code,
            )

        try:
            context = AgentContext.model_validate(
                {
                    **context.model_dump(mode="python"),
                    "tool_results": [*context.tool_results, *results],
                }
            )
        except ValidationError:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.REJECTED,
                context=context,
                errors=[AgentErrorCode.AGENT_INVALID_REQUEST],
            )

        try:
            final_output = self._call_model(request=request, context=context, trace=trace)
        except ValidationError:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.VALIDATION_FAILED,
                context=context,
                errors=[AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID],
            )
        except Exception:
            return self._finish(
                request=request,
                trace=trace,
                status=AgentRunStatus.MODEL_FAILED,
                context=context,
                errors=[AgentErrorCode.AGENT_MODEL_FAILED],
            )

        failed_results = [item for item in results if item.status != AgentToolStatus.SUCCEEDED]
        if failed_results and not final_output.warnings and not final_output.limitations:
            final_output = final_output.model_copy(
                update={
                    "limitations": [
                        self._notice(AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED)
                    ]
                }
            )
        final_validation = self.validator.validate_model_output(
            final_output,
            context=context,
            registry=self.registry,
            final=True,
        )
        if not final_validation.valid:
            return self._validation_failure(
                request=request,
                trace=trace,
                context=context,
                result=final_validation,
                output=final_output,
            )
        trace.add_event(AgentTraceEventType.RESPONSE_VALIDATED, AgentTraceStatus.SUCCEEDED)
        return self._finish(
            request=request,
            trace=trace,
            status=AgentRunStatus.TOOL_FAILED if failed_results else AgentRunStatus.SUCCEEDED,
            context=context,
            output=final_output,
            errors=(
                [AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED] if failed_results else []
            ),
        )
