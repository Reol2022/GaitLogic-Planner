from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from server.agent.enums import AgentIntent, AgentToolStatus
from server.agent.registry import AgentToolRegistry
from server.agent.schemas import AgentContext, AgentToolResult
from server.agent.tool import AgentTool
from server.agent.tools.schemas import (
    RecentTrainingInput,
    RecentTrainingOutput,
    RecentTrainingSummary,
    AgentDataQualityRead,
    TrainingDataStatus,
)
from server.domain.evidence import (
    EvidenceAssessment,
    EvidenceAssessmentStatus,
    MissingEvidence,
)
from server.services.evidence_judge_service import (
    EvidenceJudge,
    materialize_agent_evidence,
)
from server.services.evidence_reflect_service import (
    DEFAULT_TOOL_ARGUMENTS,
    EvidenceReflectPlanner,
    execute_reflect_actions,
    tool_fingerprint,
)


class RecentTool(AgentTool):
    name = "get_recent_training"
    description = "Return fictional bounded recent training facts."
    input_model = RecentTrainingInput
    output_model = RecentTrainingOutput
    allowed_intents = (AgentIntent.TODAY_RECOMMENDATION, AgentIntent.GENERAL_TRAINING_QUESTION)
    provided_fact_domains = (
        "training_volume",
        "training_frequency",
        "recent_intensity",
        "training_load",
        "plan_execution",
        "subjective_fatigue",
    )

    def __init__(self, *, empty: bool = False, fail: bool = False) -> None:
        self.empty = empty
        self.fail = fail
        self.calls = 0

    def execute(self, arguments: RecentTrainingInput, context: AgentContext):
        del arguments, context
        self.calls += 1
        if self.fail:
            raise RuntimeError("fictional failure")
        return RecentTrainingOutput(
            data_status=TrainingDataStatus.NOT_FOUND if self.empty else TrainingDataStatus.AVAILABLE,
            as_of=date(2026, 8, 20),
            items=[],
            summary=RecentTrainingSummary(
                total_sessions=0,
                total_distance_km=0,
                completed_key_sessions=0,
                rest_days=7,
            ),
            data_quality=AgentDataQualityRead(
                level="NONE" if self.empty else "HIGH",
                completeness=0 if self.empty else 1,
            ),
        )


class EmptyModel(BaseModel):
    pass


class KnowledgeOnlyTool(AgentTool):
    name = "knowledge_only"
    description = "Return knowledge only."
    input_model = EmptyModel
    output_model = EmptyModel
    allowed_intents = (AgentIntent.TODAY_RECOMMENDATION,)
    provided_fact_domains = ("training_knowledge",)

    def execute(self, arguments, context):
        del arguments, context
        return {}


def context() -> AgentContext:
    return AgentContext(
        request_id="5ef6ac0d-b831-455c-bdf5-664af0f59a50",
        user_id=7001,
        intent=AgentIntent.TODAY_RECOMMENDATION,
        current_time=datetime(2026, 8, 20, tzinfo=ZoneInfo("Asia/Shanghai")),
        timezone="Asia/Shanghai",
    )


def missing_volume() -> EvidenceAssessment:
    return EvidenceAssessment(
        domain="training_volume",
        status=EvidenceAssessmentStatus.MISSING,
        missing_evidence=[
            MissingEvidence(
                fact_keys=["recent_training"],
                description="Recent completed training facts",
                candidate_tools=["get_recent_training"],
                automatically_resolvable=True,
            )
        ],
    )


def registry(*tools: AgentTool) -> AgentToolRegistry:
    value = AgentToolRegistry()
    for tool in tools:
        value.register(tool)
    return value


def test_missing_evidence_maps_only_to_allowed_capable_tool() -> None:
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume()],
        registry=registry(RecentTool()),
        attempted_fingerprints=set(),
    )
    action = plan.actions[0]
    assert action.tool_name == "get_recent_training"
    assert action.automatically_resolvable is True


def test_already_called_tool_is_not_selected_again() -> None:
    fingerprint = tool_fingerprint(
        "get_recent_training", DEFAULT_TOOL_ARGUMENTS["get_recent_training"]
    )
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume()],
        registry=registry(RecentTool()),
        attempted_fingerprints={fingerprint},
    )
    assert plan.actions[0].already_attempted is True
    assert "NO_AUTOMATIC_EVIDENCE_SOURCE" in plan.stop_reasons


def test_unsupported_or_wrong_capability_never_invents_tool() -> None:
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume()],
        registry=registry(KnowledgeOnlyTool()),
        attempted_fingerprints=set(),
    )
    assert plan.actions[0].tool_name is None
    assert plan.actions[0].automatically_resolvable is False


def test_execution_is_bounded_and_duplicate_fingerprint_is_stable() -> None:
    tool = RecentTool()
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume(), missing_volume()],
        registry=registry(tool),
        attempted_fingerprints=set(),
    )
    results, fingerprints = execute_reflect_actions(
        plan=plan,
        registry=registry(tool),
        context=context(),
        max_actions=1,
    )
    assert len(results) == 1
    assert len(fingerprints) == 1
    assert tool.calls == 1
    assert len(
        [item for item in plan.actions if item.automatically_resolvable]
    ) == 1


def test_successful_reflect_improves_readiness() -> None:
    tool = RecentTool()
    reg = registry(tool)
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume()],
        registry=reg,
        attempted_fingerprints=set(),
    )
    results, _ = execute_reflect_actions(
        plan=plan, registry=reg, context=context(), max_actions=1
    )
    updated = context().model_copy(update={"tool_results": results})
    judged = EvidenceJudge().assess(
        relevant_domains=["training_volume"],
        evidence=materialize_agent_evidence(updated),
    )
    assert judged.assessments[0].status == EvidenceAssessmentStatus.SUFFICIENT


def test_tool_failure_is_returned_as_safe_failed_result() -> None:
    tool = RecentTool(fail=True)
    reg = registry(tool)
    plan = EvidenceReflectPlanner().plan(
        intent=AgentIntent.TODAY_RECOMMENDATION,
        assessments=[missing_volume()],
        registry=reg,
        attempted_fingerprints=set(),
    )
    results, _ = execute_reflect_actions(
        plan=plan, registry=reg, context=context(), max_actions=1
    )
    assert results[0].status == AgentToolStatus.FAILED
    assert results[0].data is None
