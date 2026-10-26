from __future__ import annotations

import logging
from collections import Counter
from time import perf_counter
from typing import Callable
from uuid import UUID

from pydantic import ValidationError

from planner_core.config import get_settings
from server.agent.context import AgentContextBuilder
from server.agent.capabilities import ExecutionContext, execution_context_scope
from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentRunStatus,
    AgentToolStatus,
    AgentTraceEventType,
    AgentTraceStatus,
)
from server.agent.errors import AgentErrorCode
from server.agent.gateway import AgentExecutionState, AgentLLMGateway
from server.agent.providers.errors import AgentProviderError
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
from server.agent.training_context_builder import merge_agent_tool_results
from server.agent.validator import AgentResponseValidator
from server.agent.prompts import build_coach_agent_system_prompt
from server.domain.evidence import EvidenceAssessmentStatus, EvidenceJudgeResult, ReflectSummary
from server.observability.tracing import NOOP_TRACER, SafeTracer, active_trace_handle
from server.observability.decision import classify_decision_outcome
from server.services.evidence_judge_service import (
    EvidenceJudge,
    materialize_agent_evidence,
    relevant_domains_for_request,
)
from server.services.evidence_reflect_service import (
    EvidenceReflectPlanner,
    execute_reflect_actions,
    successful_tool_fingerprints,
)

logger = logging.getLogger(__name__)

_ERROR_MESSAGES = {
    AgentErrorCode.AGENT_INVALID_REQUEST: "教练请求格式无效。",
    AgentErrorCode.AGENT_UNKNOWN_INTENT: "当前不支持该教练请求类型。",
    AgentErrorCode.AGENT_TOOL_NOT_FOUND: "请求所需的数据工具暂不可用。",
    AgentErrorCode.AGENT_TOOL_NOT_ALLOWED: "当前请求不允许执行该操作。",
    AgentErrorCode.AGENT_TOOL_ARGUMENTS_INVALID: "数据工具参数无效。",
    AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED: "数据工具未能返回通过校验的结果。",
    AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID: "模型返回的结构化结果无效。",
    AgentErrorCode.AGENT_MODEL_FAILED: "模型服务未能完成本次请求。",
    AgentErrorCode.AGENT_PROVIDER_DISABLED: "模型解释功能当前未启用。",
    AgentErrorCode.AGENT_PROVIDER_UNCONFIGURED: "模型解释服务尚未完成配置。",
    AgentErrorCode.AGENT_PROVIDER_UNAVAILABLE: "模型解释服务暂时不可用。",
    AgentErrorCode.AGENT_PROVIDER_RATE_LIMITED: "模型解释请求过于频繁，请稍后再试。",
    AgentErrorCode.AGENT_VALIDATION_FAILED: "模型回答未通过安全校验。",
    AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED: "本次教练请求已达到调用次数上限。",
    AgentErrorCode.AGENT_INTERNAL_ERROR: "教练服务未能安全完成本次请求。",
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
        tracer: SafeTracer | None = None,
        evidence_judge: EvidenceJudge | None = None,
        reflect_planner: EvidenceReflectPlanner | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.limits = limits or self._limits_from_settings()
        self.gateway = gateway
        self.registry = registry or AgentToolRegistry()
        self.context_builder = context_builder or AgentContextBuilder(limits=self.limits)
        self.validator = validator or AgentResponseValidator(limits=self.limits)
        self.tracer = tracer or NOOP_TRACER
        self.evidence_judge = evidence_judge or EvidenceJudge()
        self.reflect_planner = reflect_planner or EvidenceReflectPlanner()
        self.progress_callback = progress_callback
        self.last_trace: AgentTrace | None = None
        self.last_context: AgentContext | None = None
        self.last_evidence_result: EvidenceJudgeResult | None = None

    def _report_progress(self, stage: str) -> None:
        if self.progress_callback is None:
            return
        try:
            self.progress_callback(stage)
        except Exception:
            # Progress persistence is an auxiliary UI concern and must not
            # affect the safety or availability of a Coach execution.
            return

    @staticmethod
    def _limits_from_settings() -> AgentLimits:
        settings = get_settings()
        return AgentLimits(
            max_model_calls=settings.agent_max_model_calls,
            max_tool_rounds=settings.agent_max_tool_rounds,
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
            max_reflect_rounds=settings.evidence_max_reflect_rounds,
        )

    @staticmethod
    def _status_for_provider_error(error: AgentProviderError) -> AgentRunStatus:
        """Keep invalid provider output separate from availability failures."""

        if error.code == AgentErrorCode.AGENT_MODEL_OUTPUT_INVALID:
            return AgentRunStatus.VALIDATION_FAILED
        return AgentRunStatus.MODEL_FAILED

    def _judge_context(
        self,
        *,
        request: AgentRequest,
        context: AgentContext,
        operation: str = "judge",
    ) -> tuple[AgentContext, EvidenceJudgeResult]:
        result = self.evidence_judge.assess(
            relevant_domains=relevant_domains_for_request(request.intent, request.message),
            evidence=materialize_agent_evidence(context),
        )
        self.last_evidence_result = result
        values = context.model_dump(mode="python")
        values["evidence_assessments"] = result.assessments
        values["decision_readiness"] = result.decision_readiness
        updated = AgentContext.model_validate(values)
        handle = active_trace_handle()
        if handle is not None:
            counts = Counter(item.status for item in result.assessments)
            with self.tracer.span(
                handle,
                component="evidence",
                operation=operation,
                metadata={
                    "relevant_domain_count": len(result.relevant_domains),
                    "sufficient_domain_count": counts[EvidenceAssessmentStatus.SUFFICIENT],
                    "partial_domain_count": counts[EvidenceAssessmentStatus.PARTIAL],
                    "missing_domain_count": counts[EvidenceAssessmentStatus.MISSING],
                    "conflict_count": sum(len(item.conflicts) for item in result.assessments),
                },
            ):
                pass
        return updated, result

    def _reflect_context(
        self,
        *,
        request: AgentRequest,
        context: AgentContext,
        initial: EvidenceJudgeResult,
    ) -> tuple[AgentContext, EvidenceJudgeResult]:
        if self.limits.max_reflect_rounds == 0:
            values = context.model_dump(mode="python")
            values["reflect_summary"] = ReflectSummary(stop_reasons=["REFLECT_DISABLED"])
            return AgentContext.model_validate(values), initial

        attempted = successful_tool_fingerprints(context.tool_results)
        current = initial
        rounds = 0
        executed = 0
        evidence_added = 0
        no_gain = False
        stop_reasons: list[str] = []
        for round_index in range(self.limits.max_reflect_rounds):
            plan = self.reflect_planner.plan(
                intent=request.intent,
                assessments=current.assessments,
                registry=self.registry,
                attempted_fingerprints=attempted,
            )
            candidates = [
                item
                for item in plan.actions
                if item.automatically_resolvable
                and not item.already_attempted
                and item.tool_name is not None
            ]
            handle = active_trace_handle()
            if handle is not None:
                with self.tracer.span(
                    handle,
                    component="reflect",
                    operation="evaluate",
                    metadata={
                        "reflect_round": round_index + 1,
                        "candidate_action_count": len(candidates),
                    },
                ):
                    pass
            if not candidates:
                stop_reasons.extend(plan.stop_reasons or ["NO_AUTOMATIC_EVIDENCE_SOURCE"])
                break
            remaining = max(0, self.limits.max_tool_calls - len(context.tool_results))
            if remaining == 0:
                stop_reasons.append("AGENT_TOOL_CALL_BUDGET_EXHAUSTED")
                break
            rounds += 1
            before_fingerprint = current.evidence_fingerprint
            if handle is None:
                results, fingerprints = execute_reflect_actions(
                    plan=plan,
                    registry=self.registry,
                    context=context,
                    max_actions=remaining,
                )
            else:
                with self.tracer.span(
                    handle,
                    component="reflect",
                    operation="tool",
                    metadata={
                        "reflect_round": rounds,
                        "candidate_action_count": len(candidates),
                    },
                ) as span:
                    results, fingerprints = execute_reflect_actions(
                        plan=plan,
                        registry=self.registry,
                        context=context,
                        max_actions=remaining,
                    )
                    span.add_metadata(executed_action_count=len(results))
            attempted.update(fingerprints)
            executed += len(results)
            if not results:
                stop_reasons.append("NO_REFLECT_ACTION_EXECUTED")
                break
            previous_count = len(current.evidence)
            context = merge_agent_tool_results(context, results)
            context, current = self._judge_context(
                request=request,
                context=context,
                operation="rejudge",
            )
            evidence_added += max(0, len(current.evidence) - previous_count)
            if before_fingerprint == current.evidence_fingerprint:
                no_gain = True
                stop_reasons.append("NO_MARGINAL_EVIDENCE_GAIN")
                break
            if all(
                item.status
                in {
                    EvidenceAssessmentStatus.SUFFICIENT,
                    EvidenceAssessmentStatus.NOT_APPLICABLE,
                }
                for item in current.assessments
            ):
                stop_reasons.append("READINESS_SATISFIED")
                break
            if any(result.status != AgentToolStatus.SUCCEEDED for result in results):
                stop_reasons.append("REFLECT_TOOL_FAILED")
                break
        max_reached = rounds >= self.limits.max_reflect_rounds and not any(
            reason in {"READINESS_SATISFIED", "NO_MARGINAL_EVIDENCE_GAIN"}
            for reason in stop_reasons
        )
        if max_reached:
            stop_reasons.append("MAX_REFLECT_ROUNDS_REACHED")
        handle = active_trace_handle()
        if handle is not None:
            outcome = (
                "no_gain"
                if no_gain
                else "max_rounds"
                if max_reached
                else "resolved"
                if "READINESS_SATISFIED" in stop_reasons
                else "stopped"
            )
            with self.tracer.span(
                handle,
                component="reflect",
                operation="outcome",
                metadata={
                    "result": outcome,
                    "reflect_round": rounds,
                    "executed_action_count": executed,
                    "evidence_added_count": evidence_added,
                },
            ):
                pass
        values = context.model_dump(mode="python")
        values["reflect_summary"] = ReflectSummary(
            rounds=rounds,
            triggered=rounds > 0,
            executed_action_count=executed,
            evidence_added_count=evidence_added,
            no_marginal_gain=no_gain,
            max_rounds_reached=max_reached,
            stop_reasons=list(dict.fromkeys(stop_reasons)),
        )
        return AgentContext.model_validate(values), current

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
        decision = classify_decision_outcome(self.last_evidence_result)
        handle = active_trace_handle()
        if handle is not None and decision is not None:
            assessments = self.last_evidence_result.assessments
            summary = getattr(context, "reflect_summary", None) if context is not None else None
            with self.tracer.span(
                handle,
                component="decision",
                operation="outcome",
                metadata={
                    "decision_outcome": decision.value,
                    "decision_source": "evidence_judge",
                    "available_domain_count": sum(item.status == EvidenceAssessmentStatus.SUFFICIENT for item in assessments),
                    "missing_domain_count": sum(item.status == EvidenceAssessmentStatus.MISSING for item in assessments),
                    "answerable_domain_count": sum(item.status != EvidenceAssessmentStatus.MISSING for item in assessments),
                    "blocked_domain_count": sum(item.status == EvidenceAssessmentStatus.MISSING for item in assessments),
                    "reflect_triggered": bool(summary and summary.triggered),
                },
            ):
                pass
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
        final_retry: bool = False,
        execution_state: AgentExecutionState | None = None,
    ) -> AgentModelOutput:
        handle = active_trace_handle()
        if handle is None:
            return self._call_model_untraced(
                request=request,
                context=context,
                trace=trace,
                final_retry=final_retry,
                execution_state=execution_state,
            )
        with self.tracer.span(
            handle,
            component="provider",
            operation="generate",
            metadata={"provider_status": "STARTED", "operation_type": "llm"},
        ) as span:
            try:
                output = self._call_model_untraced(
                    request=request,
                    context=context,
                    trace=trace,
                    final_retry=final_retry,
                    execution_state=execution_state,
                )
            except Exception:
                reliability = getattr(self.gateway, "last_reliability", None)
                metadata = {"provider_status": "FAILED", "final_status": "FAILED"}
                if reliability is not None:
                    metadata.update(
                        {
                            "provider_kind": "chat",
                            "attempt": reliability.attempts,
                            "max_attempts": reliability.max_attempts,
                            "retried": reliability.retried,
                            "failure_category": (
                                reliability.failure_category.value
                                if reliability.failure_category is not None
                                else "PROVIDER_UNKNOWN_ERROR"
                            ),
                        }
                    )
                metadata.update(getattr(self.gateway, "last_response_metadata", {}))
                span.add_metadata(**metadata)
                span.mark_error(AgentErrorCode.AGENT_MODEL_FAILED.value)
                raise
            reliability = getattr(self.gateway, "last_reliability", None)
            metadata = {"provider_status": "SUCCEEDED", "final_status": "SUCCEEDED"}
            if reliability is not None:
                metadata.update(
                    {
                        "provider_kind": "chat",
                        "attempt": reliability.attempts,
                        "max_attempts": reliability.max_attempts,
                        "retried": reliability.retried,
                    }
                )
            metadata.update(getattr(self.gateway, "last_response_metadata", {}))
            span.add_metadata(**metadata)
            return output

    def _call_model_untraced(
        self,
        *,
        request: AgentRequest,
        context: AgentContext,
        trace: AgentTrace,
        final_retry: bool = False,
        execution_state: AgentExecutionState | None = None,
    ) -> AgentModelOutput:
        self._report_progress("GENERATING")
        started = perf_counter()
        trace.add_event(AgentTraceEventType.MODEL_CALL, AgentTraceStatus.STARTED)
        # Context construction deterministically preloads the facts required by
        # each intent. A completed result is already authoritative context, so
        # offering its tool again invites redundant provider calls and can
        # exhaust the bounded tool-call budget.
        completed_tool_names = {
            result.tool_name
            for result in context.tool_results
            if result.status == AgentToolStatus.SUCCEEDED
        }
        explain_context_complete = {
            "get_runner_state",
            "get_runner_state_history",
            "get_training_data_quality",
        }.issubset(completed_tool_names)
        if request.intent == AgentIntent.TODAY_RECOMMENDATION or (
            request.intent == AgentIntent.EXPLAIN_RUNNER_STATE
            and explain_context_complete
        ):
            # TODAY and a fully preloaded Runner State explanation are
            # narrative generations over deterministic facts. Additional
            # model-initiated tools cannot change those server-owned facts and
            # make provider tool-call loops more likely.
            tools = []
        else:
            tools = [
                definition
                for definition in self.registry.list_capabilities(request.intent)
                if definition.name not in completed_tool_names
            ]
        try:
            output = self.gateway.generate(
                system_instructions=build_coach_agent_system_prompt(
                    final_retry=final_retry,
                    retry_intent=request.intent if final_retry else None,
                ),
                user_message=request.message,
                context=context,
                tools=tools,
                trace=trace,
                execution_state=execution_state,
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

    def _retry_safe_narrative(
        self,
        *,
        request: AgentRequest,
        context: AgentContext,
        trace: AgentTrace,
        execution_state: AgentExecutionState | None = None,
    ) -> AgentResponse | None:
        """Use the remaining bounded call only for a rejected safe narrative.

        The retry has no tools and cannot change canonical facts. It is not a
        parser repair: the returned output must pass the same validator.
        """

        try:
            output = self._call_model(
                request=request,
                context=context,
                trace=trace,
                execution_state=execution_state,
                final_retry=True,
            )
        except AgentProviderError as exc:
            return self._finish(
                request=request,
                trace=trace,
                status=self._status_for_provider_error(exc),
                context=context,
                errors=[exc.code],
            )
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

        result = self._validate_output(output, context=context, final=True)
        if not result.valid:
            return self._validation_failure(
                request=request,
                trace=trace,
                context=context,
                result=result,
                output=output,
            )
        trace.add_event(AgentTraceEventType.RESPONSE_VALIDATED, AgentTraceStatus.SUCCEEDED)
        return self._finish(
            request=request,
            trace=trace,
            status=AgentRunStatus.SUCCEEDED,
            context=context,
            output=output,
        )

    def _validate_request(self, request: AgentRequest) -> AgentValidationResult:
        handle = active_trace_handle()
        if handle is None:
            return self.validator.validate_request(request)
        with self.tracer.span(
            handle,
            component="validator",
            operation="validate_request",
            metadata={"operation_type": "request_validation"},
        ) as span:
            result = self.validator.validate_request(request)
            span.add_metadata(validator_result="VALID" if result.valid else "INVALID")
            if not result.valid:
                span.set_status("REJECTED", error_code=result.errors[0].value)
            return result

    def _validate_output(
        self,
        output: AgentModelOutput,
        *,
        context: AgentContext,
        final: bool,
    ) -> AgentValidationResult:
        handle = active_trace_handle()
        if handle is None:
            return self.validator.validate_model_output(
                output, context=context, registry=self.registry, final=final
            )
        with self.tracer.span(
            handle,
            component="validator",
            operation="validate_output",
            metadata={"operation_type": "final" if final else "intermediate"},
        ) as span:
            result = self.validator.validate_model_output(
                output, context=context, registry=self.registry, final=final
            )
            span.add_metadata(validator_result="VALID" if result.valid else "INVALID")
            if not result.valid:
                span.add_metadata(
                    failure_category=self.validator.failure_category(output, result, context=context)
                )
                span.set_status("FAILED", error_code=result.errors[0].value)
            return result

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
            failure_category=(
                self.validator.failure_category(output, result, context=context)
                if output is not None
                else "OUTPUT_CONTRACT"
            ),
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
        """Run under an existing request trace, or create a safe root trace."""

        handle = active_trace_handle()
        if handle is not None:
            with self.tracer.span(
                handle,
                component="agent",
                operation="orchestrate",
                metadata={"intent": request.intent.value},
            ) as span:
                response = self._run(request, context_seed=context_seed)
                self._complete_span_from_response(span, response)
                return response
        handle = self.tracer.start_trace()
        with self.tracer.span(
            handle,
            component="agent",
            operation="request",
            metadata={"intent": request.intent.value},
            root=True,
        ) as span:
            response = self._run(request, context_seed=context_seed)
            self._complete_span_from_response(span, response)
            return response

    @staticmethod
    def _complete_span_from_response(span, response: AgentResponse) -> None:
        if response.status == AgentRunStatus.SUCCEEDED:
            return
        error_code = response.limitations[0].code if response.limitations else "AGENT_REQUEST_DEGRADED"
        span.set_status("REJECTED" if response.status == AgentRunStatus.REJECTED else "FAILED", error_code=error_code)

    def _run(
        self,
        request: AgentRequest,
        *,
        context_seed: AgentContextSeed | None = None,
    ) -> AgentResponse:
        handle = active_trace_handle()
        with execution_context_scope(ExecutionContext()):
            return self._run_traced(request, context_seed=context_seed)

    def _run_traced(
        self,
        request: AgentRequest,
        *,
        context_seed: AgentContextSeed | None = None,
    ) -> AgentResponse:
        handle = active_trace_handle()
        trace = AgentTrace(
            request_id=request.request_id,
            **({"trace_id": UUID(handle.trace_id)} if handle is not None else {}),
        )
        self.last_trace = trace
        request_validation = self._validate_request(request)
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

        context, evidence_result = self._judge_context(request=request, context=context)
        context, evidence_result = self._reflect_context(
            request=request,
            context=context,
            initial=evidence_result,
        )
        self.last_evidence_result = evidence_result

        execution_state = AgentExecutionState()
        tool_name_counts: Counter[str] = Counter()
        total_tool_calls = 0
        tool_rounds = 0
        failed_results: list[AgentToolResult] = []

        for model_round in range(self.limits.max_model_calls):
            try:
                output = self._call_model(
                    request=request,
                    context=context,
                    trace=trace,
                    execution_state=execution_state,
                )
            except AgentProviderError as exc:
                return self._finish(
                    request=request,
                    trace=trace,
                    status=self._status_for_provider_error(exc),
                    context=context,
                    errors=[exc.code],
                )
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

            if not output.tool_calls and failed_results and not output.warnings and not output.limitations:
                output = output.model_copy(
                    update={"limitations": [self._notice(AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED)]}
                )

            self._report_progress("VALIDATING")
            validation = self._validate_output(
                output, context=context, final=not output.tool_calls
            )
            if not validation.valid:
                if (
                    model_round + 1 < self.limits.max_model_calls
                    and not output.tool_calls
                    and request.intent in {
                        AgentIntent.CASUAL_CONVERSATION,
                        AgentIntent.TODAY_RECOMMENDATION,
                        AgentIntent.EXPLAIN_RUNNER_STATE,
                        AgentIntent.GENERAL_TRAINING_QUESTION,
                        AgentIntent.PERSONAL_TRAINING_ANALYSIS,
                        AgentIntent.PLAN_ADJUSTMENT_ANALYSIS,
                    }
                    and AgentErrorCode.AGENT_VALIDATION_FAILED in validation.errors
                    and self.validator.permits_narrative_repair(
                        output, validation, context=context
                    )
                ):
                    retry = self._retry_safe_narrative(
                        request=request,
                        context=context,
                        trace=trace,
                        execution_state=execution_state,
                    )
                    if retry is not None:
                        return retry
                return self._validation_failure(
                    request=request,
                    trace=trace,
                    context=context,
                    result=validation,
                    output=output,
                )
            trace.add_event(AgentTraceEventType.RESPONSE_VALIDATED, AgentTraceStatus.SUCCEEDED)

            if not output.tool_calls:
                return self._finish(
                    request=request,
                    trace=trace,
                    status=AgentRunStatus.TOOL_FAILED if failed_results else AgentRunStatus.SUCCEEDED,
                    context=context,
                    output=output,
                    errors=([AgentErrorCode.AGENT_TOOL_EXECUTION_FAILED] if failed_results else []),
                )

            tool_rounds += 1
            total_tool_calls += len(output.tool_calls)
            tool_name_counts.update(call.tool_name for call in output.tool_calls)
            if (
                tool_rounds > self.limits.max_tool_rounds
                or model_round + 1 >= self.limits.max_model_calls
                or total_tool_calls > self.limits.max_tool_calls
                or any(count > self.limits.max_same_tool_calls for count in tool_name_counts.values())
            ):
                return self._finish(
                    request=request,
                    trace=trace,
                    status=AgentRunStatus.REJECTED,
                    context=context,
                    errors=[AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED],
                )

            normalized_names = self.registry.normalize_candidates([call.tool_name for call in output.tool_calls])
            normalized_calls = [call for call in output.tool_calls if call.tool_name in normalized_names]
            round_results: list[AgentToolResult] = []
            for call in normalized_calls:
                started = perf_counter()
                trace.add_event(AgentTraceEventType.TOOL_CALL, AgentTraceStatus.STARTED, tool_name=call.tool_name)
                trace.add_event(AgentTraceEventType.MODEL_TOOL_STARTED, AgentTraceStatus.STARTED, tool_name=call.tool_name)
                result = self.registry.invoke(
                    call.tool_name, call.arguments, context, tool_call_id=call.tool_call_id
                )
                round_results.append(result)
                if result.status != AgentToolStatus.SUCCEEDED:
                    failed_results.append(result)
                status = AgentTraceStatus.SUCCEEDED if result.status == AgentToolStatus.SUCCEEDED else AgentTraceStatus.FAILED
                trace.add_event(
                    AgentTraceEventType.TOOL_CALL,
                    status,
                    tool_name=call.tool_name,
                    safe_error_code=result.safe_error_code,
                    duration_ms=(perf_counter() - started) * 1000,
                )
                trace.add_event(
                    AgentTraceEventType.MODEL_TOOL_COMPLETED,
                    status,
                    tool_name=call.tool_name,
                    safe_error_code=result.safe_error_code,
                )
            try:
                context = merge_agent_tool_results(context, round_results)
                context, evidence_result = self._judge_context(
                    request=request,
                    context=context,
                    operation="rejudge",
                )
            except ValidationError:
                return self._finish(
                    request=request,
                    trace=trace,
                    status=AgentRunStatus.REJECTED,
                    context=context,
                    errors=[AgentErrorCode.AGENT_INVALID_REQUEST],
                )

        return self._finish(
            request=request,
            trace=trace,
            status=AgentRunStatus.REJECTED,
            context=context,
            errors=[AgentErrorCode.AGENT_CALL_LIMIT_EXCEEDED],
        )
