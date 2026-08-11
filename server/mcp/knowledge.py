"""Safe MCP projections over the existing versioned training-knowledge corpus."""

from __future__ import annotations

from collections.abc import Callable
import json

from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
from server.knowledge_retrieval.errors import KnowledgeCorpusError, KnowledgeNotFoundError
from server.knowledge_retrieval.schemas import ID_PATTERN
from server.observability.tracing import active_trace_handle, active_tracer


CorpusFactory = Callable[[], KnowledgeCorpusService]


class McpKnowledgeResourceService:
    """Expose published corpus projections, never filesystem paths or indexes."""

    def __init__(self, corpus_factory: CorpusFactory = KnowledgeCorpusService) -> None:
        self._corpus_factory = corpus_factory

    @staticmethod
    def _safe_failure(code: str) -> dict[str, object]:
        return {"status": "FAILED", "error": {"code": code}}

    def _read(
        self,
        resource_type: str,
        operation: Callable[[], dict[str, object]],
        *,
        primitive: str = "resource",
        span_operation: str = "resource",
    ) -> dict[str, object]:
        tracer = active_tracer()
        handle = active_trace_handle()
        if tracer is None or handle is None:
            return operation()
        with tracer.span(
            handle,
            component="mcp",
            operation=span_operation,
            metadata={"primitive": primitive, "resource_type": resource_type},
        ) as span:
            result = operation()
            if result.get("status") == "FAILED":
                code = str(result["error"]["code"])
                span.set_status("FAILED", error_code=code)
                span.add_metadata(status="FAILED", failure_category=code)
            else:
                data = result.get("data")
                count = len(data) if isinstance(data, list) else 1
                span.add_metadata(status="SUCCEEDED", result_count=count)
            return result

    def catalog(self) -> dict[str, object]:
        def operation() -> dict[str, object]:
            try:
                return {"status": "SUCCEEDED", "data": self._corpus_factory().public_catalog()}
            except KnowledgeCorpusError:
                return self._safe_failure("DATA_UNAVAILABLE")

        return self._read("knowledge_catalog", operation)

    def document(self, document_key: str) -> dict[str, object]:
        if not ID_PATTERN.fullmatch(document_key):
            return self._safe_failure("RESOURCE_NOT_FOUND")

        def operation() -> dict[str, object]:
            try:
                return {
                    "status": "SUCCEEDED",
                    "data": self._corpus_factory().read_public_document(document_key),
                }
            except KnowledgeNotFoundError:
                return self._safe_failure("RESOURCE_NOT_FOUND")
            except KnowledgeCorpusError:
                return self._safe_failure("DATA_UNAVAILABLE")

        return self._read("knowledge_document", operation)

    def capabilities(self) -> dict[str, object]:
        return self._read(
            "capabilities",
            lambda: {
                "status": "SUCCEEDED",
                "data": {
                    "exposed_tools": [
                        "get_today_plan",
                        "get_recent_training",
                        "get_runner_state",
                        "retrieve_training_knowledge",
                    ],
                    "supported_resources": [
                        "gaitlogic://knowledge/catalog",
                        "gaitlogic://knowledge/docs/{document_key}",
                        "gaitlogic://capabilities",
                    ],
                    "read_only": True,
                    "protocol": "MCP SDK 2.0 Streamable HTTP and stdio",
                    "product_version": "0.15.0",
                },
            },
        )

    def prompt(self, prompt_name: str, renderer: Callable[[], str]) -> str:
        """Trace a prompt fetch without recording its topic or rendered text."""

        result = self._read(
            prompt_name,
            lambda: {"status": "SUCCEEDED", "data": {"text": renderer()}},
            primitive="prompt",
            span_operation="prompt",
        )
        # Prompt renderers are static templates; this fallback is intentionally
        # generic and never exposes an exception body.
        if result.get("status") == "FAILED":
            return "This prompt template is temporarily unavailable."
        return str(result["data"]["text"])


def register_knowledge_primitives(mcp, resources: McpKnowledgeResourceService) -> None:
    """Register resources and prompt templates without adding a second RAG system."""

    @mcp.resource(
        "gaitlogic://knowledge/catalog",
        name="training_knowledge_catalog",
        description="Published training-knowledge catalog without filesystem or index details.",
        mime_type="application/json",
    )
    def training_knowledge_catalog() -> str:
        return json.dumps(resources.catalog(), ensure_ascii=False, separators=(",", ":"))

    @mcp.resource(
        "gaitlogic://knowledge/docs/{document_key}",
        name="training_knowledge_document",
        description="One published allowlisted training-knowledge document by catalog key.",
        mime_type="application/json",
    )
    def training_knowledge_document(document_key: str) -> str:
        return json.dumps(resources.document(document_key), ensure_ascii=False, separators=(",", ":"))

    @mcp.resource(
        "gaitlogic://capabilities",
        name="gaitlogic_capabilities",
        description="Current public, read-only MCP capabilities.",
        mime_type="application/json",
    )
    def gaitlogic_capabilities() -> str:
        return json.dumps(resources.capabilities(), ensure_ascii=False, separators=(",", ":"))

    @mcp.prompt(
        name="training_knowledge_explain",
        description="Ask the Host to retrieve canonical training knowledge before explaining a topic.",
    )
    def training_knowledge_explain(topic: str) -> str:
        return resources.prompt(
            "training_knowledge_explain",
            lambda: (
                "Explain the selected training topic using retrieve_training_knowledge first. "
                "Use only returned canonical sources, state limitations, do not invent runner facts, "
                "and do not provide medical diagnosis. Topic: " + topic
            ),
        )

    @mcp.prompt(
        name="review_my_training",
        description="A reusable Host workflow for a read-only training review.",
    )
    def review_my_training() -> str:
        return resources.prompt(
            "review_my_training",
            lambda: (
                "First call get_recent_training and get_runner_state. When training theory is needed, "
                "call retrieve_training_knowledge. Explain only returned facts and references; do not "
                "modify a plan, create a proposal, or make a medical diagnosis."
            ),
        )
