from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from server.adaptive_workflow.graph import build_adaptive_approval_graph


def test_resume_routes_approval_payload_to_business_handler_once() -> None:
    calls: list[tuple[int, list[int]]] = []

    def approve(state):
        calls.append((state["proposal_id"], state.get("selected_item_ids", [])))
        return {"status": "applied", "proposal_id": state["proposal_id"]}

    graph = build_adaptive_approval_graph(
        checkpointer=InMemorySaver(), approval_handler=approve
    )
    config = {"configurable": {"thread_id": f"approval-{uuid4()}"}}
    paused = graph.invoke(
        {"user_id": 7, "proposal_id": 99, "decision": None, "trace_context": {}},
        config,
    )
    assert "__interrupt__" in paused

    resumed = graph.invoke(
        Command(resume={"decision": "approve", "selected_item_ids": [11, 12]}),
        config,
    )
    assert resumed["result"] == {"status": "applied", "proposal_id": 99}
    assert calls == [(99, [11, 12])]


def test_resume_routes_rejection_to_rejection_handler() -> None:
    graph = build_adaptive_approval_graph(
        checkpointer=InMemorySaver(),
        rejection_handler=lambda state: {
            "status": "rejected",
            "proposal_id": state["proposal_id"],
        },
    )
    config = {"configurable": {"thread_id": f"rejection-{uuid4()}"}}
    graph.invoke(
        {"user_id": 7, "proposal_id": 101, "decision": None, "trace_context": {}},
        config,
    )
    resumed = graph.invoke(Command(resume="reject"), config)
    assert resumed["result"] == {"status": "rejected", "proposal_id": 101}
