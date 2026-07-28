from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from time import perf_counter

from server.agent.enums import (
    AgentIntent,
    AgentRiskLevel,
    AgentRunStatus,
    AgentToolStatus,
    AgentTraceEventType,
)
from server.agent.evaluation.assertions import evaluate_assertions
from server.agent.evaluation.fixtures import (
    EVALUATION_FIXTURES,
    EVALUATION_NOW,
    EvaluationFixture,
    build_evaluation_registry,
)
from server.agent.evaluation.metrics import calculate_categories, calculate_summary
from server.agent.evaluation.schemas import (
    CoachEvaluationCase,
    CoachEvaluationReport,
    EvaluationCaseResult,
)
from server.agent.fallback import DeterministicCoachFallback
from server.agent.gateway import AgentLLMGateway
from server.agent.orchestrator import GaitLogicCoachAgent
from server.agent.prompts import COACH_AGENT_PROMPT_VERSION
from server.agent.schemas import (
    AgentContext,
    AgentLimits,
    AgentModelOutput,
    AgentNotice,
    AgentRequest,
    AgentResponse,
    AgentTodayRecommendation,
    AgentToolDefinition,
)
from server.agent.today_recommendation import canonical_today_decision, contextual_evidence
from server.agent.trace import AgentTrace
from server.agent.training_context_builder import AgentTrainingContextBuilder


class DeterministicEvaluationGateway(AgentLLMGateway):
    """Offline gateway that emits fixed structured output from fictional context."""

    def __init__(self, fixture: EvaluationFixture) -> None:
        self.fixture = fixture
        self.call_count = 0

    def generate(
        self,
        *,
        system_instructions: str,
        user_message: str,
        context: AgentContext,
        tools: list[AgentToolDefinition],
        trace: AgentTrace,
    ) -> AgentModelOutput:
        del system_instructions, tools, trace
        self.call_count += 1
        if self.fixture.provider_mode in {"disabled", "timeout"}:
            raise RuntimeError(f"fictional {self.fixture.provider_mode}")
        if self.fixture.provider_mode == "invalid_output":
            return AgentModelOutput.model_validate({"intent": "NOT_AN_INTENT"})
        if self.fixture.provider_mode == "validator_rejected":
            return AgentModelOutput(
                intent=context.intent,
                answer="I updated your official training plan.",
                risk_level=AgentRiskLevel.LOW,
            )

        limitations: list[AgentNotice] = []
        warnings: list[AgentNotice] = []
        if context.missing_reasons:
            limitations.append(
                AgentNotice(
                    code="FICTIONAL_DATA_LIMITED",
                    message="Some fictional context facts are unavailable.",
                )
            )
        if context.intent == AgentIntent.TODAY_RECOMMENDATION:
            evaluation = context.today_evaluation or {}
            decision = canonical_today_decision(evaluation)
            planned = str((context.today_workout or {}).get("workout_status") or "UNKNOWN")
            risk_value = str(evaluation.get("risk_level") or "UNKNOWN")
            risk = (
                AgentRiskLevel(risk_value)
                if risk_value in AgentRiskLevel._value2member_map_
                else AgentRiskLevel.UNKNOWN
            )
            if decision == "UNKNOWN" and not limitations:
                limitations.append(
                    AgentNotice(
                        code="FICTIONAL_DATA_LIMITED",
                        message="Fictional data is insufficient for a definite decision.",
                    )
                )
            if risk == AgentRiskLevel.HIGH:
                warnings.append(
                    AgentNotice(
                        code="HIGH_RISK_REVIEW_REQUIRED",
                        message="Review the fictional high-risk signal before training.",
                    )
                )
            recommendation = AgentTodayRecommendation(
                decision=decision,
                planned_workout_status=planned,
                headline=f"Deterministic fictional decision: {decision}.",
                key_evidence=contextual_evidence(context)[:5],
                data_quality=str((context.data_quality or {}).get("data_status") or "UNKNOWN"),
            )
            return AgentModelOutput(
                intent=context.intent,
                answer=self.fixture.safe_answer
                or f"The read-only Coach preserves the deterministic decision {decision}.",
                summary=f"Fictional evaluation: {decision}",
                risk_level=risk,
                warnings=warnings,
                limitations=limitations,
                today_recommendation=recommendation,
            )

        answer = self.fixture.safe_answer
        if answer is None and context.intent == AgentIntent.EXPLAIN_RUNNER_STATE:
            state = str((context.runner_state or {}).get("overall_state") or "UNKNOWN")
            answer = f"The fictional Runner State is {state}; evidence and limitations remain visible."
        if answer is None:
            answer = "The Coach can explain registered public training rules using read-only tools."
        return AgentModelOutput(
            intent=context.intent,
            answer=answer,
            summary="Fictional read-only Coach response.",
            risk_level=AgentRiskLevel.UNKNOWN,
            warnings=warnings,
            limitations=limitations,
        )


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def materialize_evaluation_fallback_response(
    *,
    request: AgentRequest,
    response: AgentResponse,
    context: AgentContext,
    agent: GaitLogicCoachAgent,
) -> AgentResponse:
    fallback = DeterministicCoachFallback().build(
        intent=request.intent,
        message=request.message,
        context=context,
        trace=agent.last_trace,
    )
    return response.model_copy(
        update={
            "answer": fallback.answer,
            "summary": fallback.summary,
            "risk_level": fallback.risk_level,
            "warnings": fallback.warnings,
            "limitations": fallback.limitations,
            "today_recommendation": fallback.today_recommendation,
        }
    )


class CoachAgentEvaluationRunner:
    def __init__(self, *, user_id: int = 70001) -> None:
        self.user_id = user_id
        self.limits = AgentLimits()

    def run_case(self, case: CoachEvaluationCase) -> EvaluationCaseResult:
        started = perf_counter()
        fixture = EVALUATION_FIXTURES[case.fixture]
        registry = build_evaluation_registry(fixture)
        context_builder = AgentTrainingContextBuilder(
            registry=registry,
            limits=self.limits,
            clock=lambda: EVALUATION_NOW,
        )
        gateway = DeterministicEvaluationGateway(fixture)
        agent = GaitLogicCoachAgent(
            gateway=gateway,
            registry=registry,
            context_builder=context_builder,
            limits=self.limits,
        )
        request = AgentRequest.for_authenticated_user(
            user_id=self.user_id,
            message=case.question,
            intent=case.intent,
        )
        response = agent.run(request)
        context = agent.last_context
        has_tool_failure = context is not None and any(
            result.status != AgentToolStatus.SUCCEEDED for result in context.tool_results
        )
        used_fallback = context is not None and (
            response.status != AgentRunStatus.SUCCEEDED or has_tool_failure
        )
        if used_fallback and context is not None:
            response = materialize_evaluation_fallback_response(
                request=request,
                response=response,
                context=context,
                agent=agent,
            )
        public_status = (
            "SUCCEEDED"
            if response.status == AgentRunStatus.SUCCEEDED and not has_tool_failure
            else "DEGRADED"
            if context is not None
            else "UNAVAILABLE"
        )

        events = agent.last_trace.events if agent.last_trace else []
        context_tools = [
            event.tool_name
            for event in events
            if event.event_type == AgentTraceEventType.CONTEXT_TOOL_COMPLETED
            and event.tool_name is not None
        ]
        model_tools = [
            event.tool_name
            for event in events
            if event.event_type == AgentTraceEventType.MODEL_TOOL_COMPLETED
            and event.tool_name is not None
        ]
        assertions, unsupported, violations = evaluate_assertions(
            case=case,
            response=response,
            public_status=public_status,
            context_tools=context_tools,
            model_tools=model_tools,
        )
        actual_tools = set(context_tools) | set(model_tools)
        expected_tools = set(case.expected_context_tools) | set(case.expected_model_tools)
        safe_errors = sorted(
            {
                item.safe_error_code.value
                for item in response.tool_calls
                if item.safe_error_code is not None
            }
            | {
                item.code
                for item in response.limitations
                if item.code.startswith("AGENT_")
            }
        )
        recommendation = response.today_recommendation
        warning_codes = {item.code for item in response.warnings}
        tool_arguments_valid = all(
            item.status != AgentToolStatus.INVALID_ARGUMENTS for item in response.tool_calls
        )
        return EvaluationCaseResult(
            case_id=case.case_id,
            category=case.category,
            passed=all(item.passed for item in assertions) and tool_arguments_valid,
            intent=case.intent,
            actual_intent=response.intent,
            status=public_status,
            expected_tools=sorted(expected_tools),
            actual_context_tools=context_tools,
            actual_model_tools=model_tools,
            expected_decision=case.expected_decision,
            actual_decision=(
                recommendation.decision if recommendation is not None else None
            ),
            expected_planned_status=case.expected_planned_status,
            actual_planned_status=(
                recommendation.planned_workout_status
                if recommendation is not None
                else None
            ),
            assertions=assertions,
            safe_error_codes=safe_errors,
            duration_ms=round((perf_counter() - started) * 1000, 3),
            used_fallback=used_fallback,
            required_tool_hits=len(actual_tools & expected_tools),
            required_tool_total=len(expected_tools),
            forbidden_tool_called=bool(actual_tools & set(case.forbidden_tools)),
            tool_arguments_valid=tool_arguments_valid,
            warning_retained=(
                set(case.required_warning_codes).issubset(warning_codes)
                if case.required_warning_codes
                else None
            ),
            limitation_retained=(
                bool(response.limitations) if case.requires_limitation else None
            ),
            unsupported_claim_found=bool(unsupported),
            rule_violation_found=bool(violations),
        )

    def run(
        self,
        cases: list[CoachEvaluationCase],
        *,
        fail_fast: bool = False,
    ) -> CoachEvaluationReport:
        started = perf_counter()
        results: list[EvaluationCaseResult] = []
        for case in cases:
            result = self.run_case(case)
            results.append(result)
            if fail_fast and not result.passed:
                break
        return CoachEvaluationReport(
            prompt_version=COACH_AGENT_PROMPT_VERSION,
            git_commit=_git_commit(),
            generated_at=datetime.now(timezone.utc),
            duration_ms=round((perf_counter() - started) * 1000, 3),
            summary=calculate_summary(results),
            categories=calculate_categories(results),
            cases=results,
        )
