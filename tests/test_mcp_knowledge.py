"""Knowledge Tool, Resources and Prompts use fictional canonical corpus data."""

from __future__ import annotations

import asyncio
import json

from mcp import Client
import pytest

from server.agent.tools.knowledge_tools import (
    KnowledgeToolResultItem,
    RetrieveTrainingKnowledgeOutput,
)
from server.knowledge_retrieval.enums import KnowledgeCategory, KnowledgeEvidenceLevel
from server.knowledge_retrieval.errors import KnowledgeNotFoundError, KnowledgeValidationError
from server.mcp.context import McpExecutionContext, McpRequestIdentity
from server.mcp.knowledge import McpKnowledgeResourceService
from server.mcp.server import create_mcp_server
from server.observability.metrics import InMemoryMetricsSink, MetricsRecorder, MetricsTraceSink
from server.observability.tracing import FanoutTraceSink, InMemoryTraceSink, SafeTracer
from tests.agent_tool_fakes import FakeDependencies


class _FakeKnowledgeTool:
    def execute(self, arguments, _context):
        assert arguments.query == "threshold training"
        return RetrieveTrainingKnowledgeOutput(
            query_status="SUCCEEDED",
            index_id="knowledge-aaaaaaaaaaaaaaaaaaaaaaaa",
            corpus_root_hash="a" * 64,
            results=[
                KnowledgeToolResultItem(
                    knowledge_reference_id="knowledge_1",
                    chunk_id="internal-chunk-01",
                    document_id="fictional-threshold-guide",
                    title="Fictional Threshold Guide",
                    section="Purpose",
                    excerpt="A fictional, bounded training explanation.",
                    category=KnowledgeCategory.THRESHOLD,
                    source_id="fictional-source",
                    source_title="Fictional Source",
                    knowledge_version="1.0.0",
                    evidence_level=KnowledgeEvidenceLevel.SECONDARY,
                    score=0.99,
                )
            ],
        )


class _FakeCorpus:
    def public_catalog(self):
        return [
            {
                "document_key": "fictional-threshold-guide",
                "title": "Fictional Threshold Guide",
                "category": "THRESHOLD",
                "version": "1.0.0",
                "evidence_level": "SECONDARY",
                "source": "Fictional Source",
                "limitations": [],
            }
        ]

    def read_public_document(self, document_key: str):
        if document_key != "fictional-threshold-guide":
            raise KnowledgeNotFoundError("fictional")
        return {
            **self.public_catalog()[0],
            "content": "Fictional published summary only.",
        }


def _server():
    return create_mcp_server(
        McpExecutionContext(
            identity_provider=lambda: McpRequestIdentity(901),
            session_factory=lambda: object(),
        ),
        dependencies_factory=lambda _session: FakeDependencies(),
        knowledge_tool_factory=lambda: _FakeKnowledgeTool(),
        knowledge_resource_service=McpKnowledgeResourceService(corpus_factory=_FakeCorpus),
    )


def _run(coro):
    return asyncio.run(coro)


def test_knowledge_tool_reuses_canonical_output_without_internal_index_fields() -> None:
    async def run():
        async with Client(_server()) as client:
            return await client.call_tool("retrieve_training_knowledge", {"query": "threshold training"})

    result = _run(run())
    payload = result.structured_content
    assert payload["status"] == "SUCCEEDED"
    assert payload["data"]["references"][0]["reference_id"] == "knowledge_1"
    serialized = json.dumps(payload)
    for forbidden in ("internal-chunk-01", "knowledge-aaaaaaaa", "corpus_root_hash", "score", "vector"):
        assert forbidden not in serialized


def test_knowledge_tool_requires_trusted_identity_and_degrades_when_index_is_unavailable() -> None:
    missing_identity = create_mcp_server(
        McpExecutionContext(identity_provider=lambda: None, session_factory=lambda: object()),
        dependencies_factory=lambda _session: FakeDependencies(),
        knowledge_tool_factory=lambda: _FakeKnowledgeTool(),
    )
    unavailable = create_mcp_server(
        McpExecutionContext(identity_provider=lambda: McpRequestIdentity(901), session_factory=lambda: object()),
        dependencies_factory=lambda _session: FakeDependencies(),
        knowledge_tool_factory=lambda: None,
    )
    for server, expected in ((missing_identity, "AUTH_CONTEXT_MISSING"), (unavailable, "DATA_UNAVAILABLE")):
        result = _run(
            _call_knowledge(server, {"query": "threshold training"})
        )
        assert result.structured_content["status"] == "FAILED"
        assert result.structured_content["error"]["code"] == expected


async def _call_knowledge(server, arguments: dict):
    async with Client(server) as client:
        return await client.call_tool("retrieve_training_knowledge", arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "threshold training", "user_id": 1},
        {"query": "threshold training", "index_id": "knowledge-aaaaaaaaaaaaaaaaaaaaaaaa"},
        {"query": "threshold training", "categories": ["NOT_A_CATEGORY"]},
    ],
)
def test_knowledge_tool_rejects_identity_and_invalid_filter_arguments(arguments) -> None:
    async def run():
        async with Client(_server()) as client:
            return await client.call_tool("retrieve_training_knowledge", arguments)

    result = _run(run())
    assert result.is_error is True
    assert "INVALID_ARGUMENT" in str(result.content)


def test_resources_are_allowlisted_and_prompts_are_templates_not_database_calls() -> None:
    async def run():
        async with Client(_server()) as client:
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            catalog = await client.read_resource("gaitlogic://knowledge/catalog")
            document = await client.read_resource("gaitlogic://knowledge/docs/fictional-threshold-guide")
            prompts = await client.list_prompts()
            prompt = await client.get_prompt("training_knowledge_explain", {"topic": "threshold"})
            return resources, templates, catalog, document, prompts, prompt

    resources, templates, catalog, document, prompts, prompt = _run(run())
    assert {str(item.uri) for item in resources.resources} == {
        "gaitlogic://knowledge/catalog",
        "gaitlogic://capabilities",
    }
    assert {str(item.uri_template) for item in templates.resource_templates} == {
        "gaitlogic://knowledge/docs/{document_key}"
    }
    assert "relative_path" not in catalog.contents[0].text
    assert "Fictional published summary only." in document.contents[0].text
    assert {item.name for item in prompts.prompts} == {"training_knowledge_explain", "review_my_training"}
    assert "retrieve_training_knowledge" in prompt.messages[0].content.text
    assert "user_id" not in prompt.messages[0].content.text


def test_document_resource_rejects_non_catalog_and_traversal_keys_without_file_access() -> None:
    service = McpKnowledgeResourceService(corpus_factory=_FakeCorpus)
    assert service.document("not-in-catalog")["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert service.document("../../secrets")["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_corpus_failure_returns_safe_data_unavailable_without_exception_text() -> None:
    class BrokenCorpus:
        def public_catalog(self):
            raise KnowledgeValidationError("C:/private/corpus/index is invalid")

    payload = McpKnowledgeResourceService(corpus_factory=BrokenCorpus).catalog()
    assert payload == {"status": "FAILED", "error": {"code": "DATA_UNAVAILABLE"}}


def test_knowledge_resources_and_prompts_emit_safe_trace_and_metrics() -> None:
    trace_sink = InMemoryTraceSink()
    metric_sink = InMemoryMetricsSink()
    tracer = SafeTracer(
        FanoutTraceSink(trace_sink, MetricsTraceSink(MetricsRecorder(metric_sink)))
    )
    service = McpKnowledgeResourceService(corpus_factory=_FakeCorpus)

    with tracer.request(component="mcp", operation="request", metadata={"transport": "stdio"}):
        assert service.catalog()["status"] == "SUCCEEDED"
        assert "retrieve_training_knowledge" in service.prompt(
            "training_knowledge_explain", lambda: "Call retrieve_training_knowledge first."
        )

    resource_span, prompt_span = [
        span for span in trace_sink.spans if span.component == "mcp" and span.operation in {"resource", "prompt"}
    ]
    assert (resource_span.operation, prompt_span.operation) == ("resource", "prompt")
    assert resource_span.metadata["primitive"] == "resource"
    assert prompt_span.metadata["primitive"] == "prompt"
    assert "query" not in str(prompt_span.metadata)
    assert metric_sink.counter("mcp_resource_read_count") == 1
    assert metric_sink.counter("mcp_prompt_get_count") == 1
