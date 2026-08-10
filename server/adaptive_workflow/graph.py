from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class AdaptiveApprovalState(TypedDict):
    user_id: int
    proposal_id: int
    decision: str | None


def request_human_approval(state: AdaptiveApprovalState) -> dict:
    decision = interrupt(
        {
            "proposal_id": state["proposal_id"],
            "allowed_actions": ["approve", "reject"],
        }
    )
    if decision not in {"approve", "reject"}:
        raise ValueError("Human decision must be approve or reject")
    return {"decision": decision}


def build_adaptive_approval_graph(*, checkpointer):
    graph = StateGraph(AdaptiveApprovalState)
    graph.add_node("human_interrupt", request_human_approval)
    graph.add_edge(START, "human_interrupt")
    graph.add_edge("human_interrupt", END)
    return graph.compile(checkpointer=checkpointer)
