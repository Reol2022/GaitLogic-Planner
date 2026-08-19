from __future__ import annotations

from datetime import date

from planner_core.weekly_review.aggregation import build_weekly_facts
from planner_core.weekly_review.schemas import (
    PlannedSessionFact,
    WeeklyFactsRequest,
    WeeklyPeriod,
    WorkoutSessionFact,
)
from server.weekly_review_graph.schemas import WeeklyReviewDraft, WeeklyReviewState
from server.weekly_review_graph.schemas import PlanDesignAnalysis, WeeklyReviewAnalysis
from planner_core.adaptive_plan.schemas import PlanValue, ProposalCandidateChange, TargetPlanFact
from planner_core.enums import PlanAdjustmentAction
from server.weekly_review_graph.adapters import DeterministicProposalMaterializer
from server.weekly_review_graph.workflow import build_weekly_review_graph


START = date(2026, 7, 6)
END = date(2026, 7, 12)


def weekly_facts():
    return build_weekly_facts(
        period=WeeklyPeriod(
            week_start=START,
            week_end=END,
            timezone="Asia/Shanghai",
        ),
        plans=[
            PlannedSessionFact(
                plan_id=1,
                session_date=START,
                main_type="easy",
                distance_km=8,
            )
        ],
        logs=[
            WorkoutSessionFact(
                log_id=1,
                planned_workout_id=1,
                activity_date=START,
                main_type="easy",
                distance_km=8,
                duration_minutes=48,
                status="completed_normal",
            )
        ],
        runner_state_samples=[],
        as_of_date=END,
    )


def initial_state() -> WeeklyReviewState:
    request = WeeklyFactsRequest(
        user_id=7,
        week_start=START,
        week_end=END,
        timezone="Asia/Shanghai",
    )
    return WeeklyReviewState(user_id=7, request=request)


def valid_draft(**updates) -> WeeklyReviewDraft:
    values = {
        "overview": "本周训练按确定性事实完成。",
        "completion_summary": "计划一项，完成一项。",
        "key_session_summary": "本周没有计划关键课。",
        "deviation_summary": "没有实质偏差。",
        "fatigue_and_risk": "恢复历史不足，不作额外推断。",
        "next_week_focus": ["继续记录训练事实。"],
    }
    values.update(updates)
    return WeeklyReviewDraft(**values)


def invoke(*, generator=None, retriever=None):
    graph = build_weekly_review_graph(
        facts_loader=lambda request: weekly_facts(),
        generator=generator or (lambda state: valid_draft()),
        knowledge_retriever=retriever,
    )
    return WeeklyReviewState.model_validate(
        graph.invoke(initial_state().model_dump(mode="python"))
    )


def test_graph_executes_all_core_nodes_and_returns_canonical_facts() -> None:
    result = invoke()
    assert result.status.value == "COMPLETED"
    assert result.final_review is not None
    assert result.final_review.weekly_facts.result_hash == weekly_facts().result_hash
    assert result.final_review.rule_results == ["NO_MATERIAL_WEEKLY_DEVIATION"]


def test_rag_disabled_is_a_safe_limitation() -> None:
    result = invoke()
    assert "KNOWLEDGE_RETRIEVAL_DISABLED" in result.final_review.limitations
    assert result.final_review.knowledge_references == []


def test_embedding_or_retrieval_failure_does_not_change_weekly_facts() -> None:
    def failed(**kwargs):
        raise RuntimeError("fictional provider failure")

    result = invoke(retriever=failed)
    assert "KNOWLEDGE_RETRIEVAL_UNAVAILABLE" in result.final_review.limitations
    assert result.final_review.weekly_facts.completed.actual_distance_km == 8


def test_chat_provider_failure_uses_deterministic_fallback() -> None:
    def failed(state):
        raise RuntimeError("fictional chat failure")

    result = invoke(generator=failed)
    assert result.final_review.fallback_used is True
    assert "MODEL_EXPLANATION_UNAVAILABLE" in result.final_review.limitations


def test_validator_rejects_plan_mutation_claim_and_preserves_warnings() -> None:
    result = invoke(
        generator=lambda state: valid_draft(
            overview="已修改训练计划。",
        )
    )
    assert result.final_review.fallback_used is True
    assert result.final_review.warnings == weekly_facts().classification.warnings


def test_unknown_knowledge_reference_routes_to_fallback() -> None:
    result = invoke(
        generator=lambda state: valid_draft(
            knowledge_reference_ids=["knowledge_99"]
        )
    )
    assert result.final_review.fallback_used is True
    assert result.final_review.knowledge_references == []


def test_public_result_does_not_expose_internal_user_identity() -> None:
    result = invoke()
    payload = result.final_review.model_dump(mode="json")
    assert "user_id" not in payload
    assert "trace_context" not in payload
    assert "provider" not in payload


def test_graph_contains_named_nodes_edges_and_conditional_branch() -> None:
    graph = build_weekly_review_graph(
        facts_loader=lambda request: weekly_facts(),
        generator=lambda state: valid_draft(),
    )
    names = set(graph.get_graph().nodes)
    assert {
        "load_weekly_facts",
        "evaluate_weekly_rules",
        "retrieve_training_knowledge",
        "generate_weekly_review",
        "validate_weekly_review",
        "fallback_weekly_review",
        "finalize_weekly_review",
        "generate_plan_design",
        "materialize_proposal",
    }.issubset(names)


def test_weekly_analysis_then_independent_plan_design_and_materialize() -> None:
    calls = []

    def analyze(state):
        calls.append(("weekly", state.plan_design))
        return WeeklyReviewAnalysis(
            overall_assessment="稳定",
            execution_assessment="完成",
            load_assessment="负荷稳定",
            key_session_assessment="关键课完成",
            recovery_assessment="恢复事实有限",
            intensity_assessment="强度稳定",
            next_week_constraints=["不增加负荷"],
            recommended_direction=["维持"],
        )

    def design(state):
        calls.append(("plan", state.weekly_analysis.overall_assessment))
        return PlanDesignAnalysis(
            volume_direction="reduce",
            intensity_direction="maintain",
            quality_session_count=0,
            key_session_strategy="维持结构",
            long_run_strategy="保守",
            recovery_spacing="留出恢复间隔",
            reason_summary="依据结构化周复盘减量",
            candidate_adjustments=[
                ProposalCandidateChange(
                    plan_id=10,
                    action=PlanAdjustmentAction.reduce,
                    after=PlanValue(content="轻松跑", distance_km=6, main_type="easy"),
                    reason="保守调整",
                    rule_evidence=["NO_MATERIAL_WEEKLY_DEVIATION"],
                )
            ],
        )

    target = TargetPlanFact(
        plan_id=10,
        user_id=7,
        workout_date=date(2026, 7, 13),
        value=PlanValue(content="轻松跑", distance_km=8, main_type="easy"),
    )
    graph = build_weekly_review_graph(
        facts_loader=lambda request: weekly_facts(),
        generator=analyze,
        plan_designer=design,
        proposal_materializer=DeterministicProposalMaterializer(),
    )
    state = initial_state().model_copy(update={"target_plans": [target]})
    result = WeeklyReviewState.model_validate(graph.invoke(state.model_dump(mode="python")))
    assert calls == [("weekly", None), ("plan", "稳定")]
    assert result.plan_design is not None
    assert result.proposal.changes[0].after.distance_km == 6
    assert result.proposal.week_start == date(2026, 7, 13)
