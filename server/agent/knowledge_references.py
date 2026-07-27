from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from server.agent.enums import AgentToolStatus
from server.agent.schemas import (
    AgentContext,
    AgentKnowledgeReference,
    AgentToolResult,
)
from server.agent.tools.knowledge_tools import (
    KnowledgeToolResultItem,
    RetrieveTrainingKnowledgeOutput,
)

KNOWLEDGE_TOOL_NAME = "retrieve_training_knowledge"


@dataclass(frozen=True)
class KnowledgeReferenceCatalog:
    items: dict[str, KnowledgeToolResultItem]
    attempted: bool
    failed: bool
    empty: bool
    limitations: tuple[str, ...]


def build_knowledge_reference_catalog(
    context: AgentContext,
) -> KnowledgeReferenceCatalog:
    tool_results = [
        item for item in context.tool_results if item.tool_name == KNOWLEDGE_TOOL_NAME
    ]
    if len(tool_results) > 1:
        raise ValueError("Only one knowledge retrieval call is allowed per request")
    if not tool_results:
        return KnowledgeReferenceCatalog({}, False, False, False, ())
    result: AgentToolResult = tool_results[0]
    if result.status != AgentToolStatus.SUCCEEDED or not isinstance(result.data, dict):
        return KnowledgeReferenceCatalog({}, True, True, False, ())
    try:
        output = RetrieveTrainingKnowledgeOutput.model_validate(result.data)
    except ValidationError as exc:
        raise ValueError("Knowledge tool result is not canonical") from exc
    items = {item.knowledge_reference_id: item for item in output.results}
    if len(items) != len(output.results):
        raise ValueError("Knowledge tool result contains duplicate reference IDs")
    expected = [f"knowledge_{index}" for index in range(1, len(items) + 1)]
    if list(items) != expected:
        raise ValueError("Knowledge reference IDs do not follow retrieval rank")
    return KnowledgeReferenceCatalog(
        items=items,
        attempted=True,
        failed=False,
        empty=output.query_status == "EMPTY",
        limitations=tuple(output.limitations),
    )


def materialize_knowledge_references(
    reference_ids: list[str],
    context: AgentContext,
) -> list[AgentKnowledgeReference]:
    catalog = build_knowledge_reference_catalog(context)
    if len(reference_ids) != len(set(reference_ids)):
        raise ValueError("Knowledge reference IDs must be unique")
    if any(reference_id not in catalog.items for reference_id in reference_ids):
        raise ValueError("Knowledge reference does not exist in this request")
    selected = set(reference_ids)
    return [
        AgentKnowledgeReference(
            document_id=item.document_id,
            title=item.title,
            section=item.section,
            source_id=item.source_id,
            source_title=item.source_title,
            knowledge_version=item.knowledge_version,
            evidence_level=item.evidence_level.value,
            excerpt=item.excerpt,
            limitations=item.limitations,
        )
        for reference_id, item in catalog.items.items()
        if reference_id in selected
    ]
