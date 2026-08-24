from __future__ import annotations

from typing import Any

from langgraph.types import Command

from planner_core.database.session import SessionLocal
from server.adaptive_workflow.checkpointer import SQLAlchemyCheckpointSaver
from server.adaptive_workflow.graph import AdaptiveApprovalState, build_adaptive_approval_graph
from server.observability.factory import get_configured_tracer
from server.schemas.adaptive_plan import AdaptiveApprovalResult
from server.schemas.weekly_review import PlanAdjustmentApplyResponse
from server.services.adaptive_plan_approval_service import AdaptivePlanApprovalService
from server.services import plan_adjustment_apply_service


def _thread_id(kind: str, user_id: int, record_id: int) -> str:
    return f"{kind}:{user_id}:{record_id}"


def _config(kind: str, user_id: int, record_id: int) -> dict[str, Any]:
    return {
        "configurable": {
            "thread_id": _thread_id(kind, user_id, record_id),
        }
    }


def _graph(kind: str):
    saver = SQLAlchemyCheckpointSaver(SessionLocal)

    def approve(state: AdaptiveApprovalState) -> dict[str, Any]:
        with SessionLocal() as db:
            if kind == "weekly-draft":
                result = plan_adjustment_apply_service.apply_adjustment_draft(
                    db,
                    state["user_id"],
                    state["proposal_id"],
                    state.get("selected_item_ids", []),
                )
                return result.model_dump(mode="json")
            result = AdaptivePlanApprovalService(tracer=get_configured_tracer()).approve(
                db,
                user_id=state["user_id"],
                proposal_id=state["proposal_id"],
            )
            return result.model_dump(mode="json")

    def reject(state: AdaptiveApprovalState) -> dict[str, Any]:
        with SessionLocal() as db:
            if kind == "weekly-draft":
                draft = plan_adjustment_apply_service.reject_adjustment_draft(
                    db, state["user_id"], state["proposal_id"]
                )
                return {"draft_id": draft.id, "status": draft.status.value}
            result = AdaptivePlanApprovalService(tracer=get_configured_tracer()).reject(
                db,
                user_id=state["user_id"],
                proposal_id=state["proposal_id"],
            )
            return result.model_dump(mode="json")

    return build_adaptive_approval_graph(
        checkpointer=saver,
        tracer=get_configured_tracer(),
        approval_handler=approve,
        rejection_handler=reject,
    )


def ensure_pending(*, kind: str, user_id: int, record_id: int) -> None:
    graph = _graph(kind)
    config = _config(kind, user_id, record_id)
    snapshot = graph.get_state(config)
    if snapshot.values:
        return
    graph.invoke(
        {
            "user_id": user_id,
            "proposal_id": record_id,
            "decision": None,
            "trace_context": {},
        },
        config,
    )


def approve_weekly_draft(
    *, user_id: int, draft_id: int, selected_item_ids: list[int]
) -> PlanAdjustmentApplyResponse:
    ensure_pending(kind="weekly-draft", user_id=user_id, record_id=draft_id)
    result = _graph("weekly-draft").invoke(
        Command(resume={"decision": "approve", "selected_item_ids": selected_item_ids}),
        _config("weekly-draft", user_id, draft_id),
    )
    response = PlanAdjustmentApplyResponse.model_validate(result["result"])
    if response.status.value == "partially_applied":
        SQLAlchemyCheckpointSaver(SessionLocal).delete_thread(
            _thread_id("weekly-draft", user_id, draft_id)
        )
        ensure_pending(kind="weekly-draft", user_id=user_id, record_id=draft_id)
    return response


def reject_weekly_draft(*, user_id: int, draft_id: int) -> None:
    ensure_pending(kind="weekly-draft", user_id=user_id, record_id=draft_id)
    _graph("weekly-draft").invoke(
        Command(resume="reject"), _config("weekly-draft", user_id, draft_id)
    )


def approve_adaptive_proposal(*, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
    ensure_pending(kind="adaptive-proposal", user_id=user_id, record_id=proposal_id)
    result = _graph("adaptive-proposal").invoke(
        Command(resume="approve"), _config("adaptive-proposal", user_id, proposal_id)
    )
    return AdaptiveApprovalResult.model_validate(result["result"])


def reject_adaptive_proposal(*, user_id: int, proposal_id: int) -> AdaptiveApprovalResult:
    ensure_pending(kind="adaptive-proposal", user_id=user_id, record_id=proposal_id)
    result = _graph("adaptive-proposal").invoke(
        Command(resume="reject"), _config("adaptive-proposal", user_id, proposal_id)
    )
    return AdaptiveApprovalResult.model_validate(result["result"])
