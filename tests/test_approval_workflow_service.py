from server.services.approval_workflow_service import _config


def test_approval_workflow_uses_root_checkpoint_namespace() -> None:
    """A root graph must not be configured as a LangGraph subgraph."""
    assert _config("weekly-draft", 7, 42) == {
        "configurable": {"thread_id": "weekly-draft:7:42"}
    }
