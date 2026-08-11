from __future__ import annotations

from typing import Protocol

from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.hybrid.fusion import ReciprocalRankFusion
from server.knowledge_retrieval.retrieval_schemas import KnowledgeRetrievalRequest, KnowledgeRetrievalResponse
from server.observability.tracing import active_trace_handle, active_tracer


class _Retriever(Protocol):
    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse: ...


class HybridKnowledgeRetriever:
    """Fuse independently filtered Dense and BM25 candidates at application level."""

    def __init__(
        self,
        *,
        dense_retriever: _Retriever,
        bm25_retriever: _Retriever,
        dense_candidate_depth: int = 8,
        bm25_candidate_depth: int = 8,
        fusion: ReciprocalRankFusion | None = None,
    ) -> None:
        if not 4 <= dense_candidate_depth <= 12 or not 4 <= bm25_candidate_depth <= 12:
            raise ValueError("Hybrid candidate depths must be between 4 and 12.")
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.dense_candidate_depth = dense_candidate_depth
        self.bm25_candidate_depth = bm25_candidate_depth
        self.fusion = fusion or ReciprocalRankFusion()

    @staticmethod
    def _safe_error(error: Exception) -> str:
        return "DENSE_UNAVAILABLE" if "embedding" in error.__class__.__name__.lower() else "RETRIEVER_UNAVAILABLE"

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse:
        dense_request = request.model_copy(update={"top_k": max(request.top_k, self.dense_candidate_depth)})
        bm25_request = request.model_copy(update={"top_k": max(request.top_k, self.bm25_candidate_depth)})
        tracer, handle = active_tracer(), active_trace_handle()
        dense_response = bm25_response = None
        dense_failure = bm25_failure = None

        def retrieve_sources() -> None:
            nonlocal dense_response, bm25_response, dense_failure, bm25_failure
            try:
                dense_response = self.dense_retriever.retrieve(dense_request)
            except Exception as exc:
                dense_failure = exc
            try:
                bm25_response = self.bm25_retriever.retrieve(bm25_request)
            except Exception as exc:
                bm25_failure = exc

        if tracer is None or handle is None:
            retrieve_sources()
        else:
            with tracer.span(handle, component="knowledge", operation="hybrid_retrieval", metadata={"retrieval_strategy": "hybrid", "fusion_method": self.fusion.name}) as span:
                retrieve_sources()
                span.add_metadata(
                    dense_result_count=len(dense_response.results) if dense_response else 0,
                    bm25_result_count=len(bm25_response.results) if bm25_response else 0,
                )
                if dense_failure is not None or bm25_failure is not None:
                    span.mark_fallback("HYBRID_SOURCE_UNAVAILABLE")
                if dense_failure is not None and bm25_failure is not None:
                    span.mark_error("HYBRID_SOURCES_UNAVAILABLE")

        if dense_response is None and bm25_response is None:
            raise KnowledgeRetrievalError("Hybrid knowledge retrieval is unavailable.")
        dense_results = dense_response.results if dense_response else []
        bm25_results = bm25_response.results if bm25_response else []
        fused = self.fusion.fuse(
            dense_chunk_ids=[item.chunk_id for item in dense_results],
            bm25_chunk_ids=[item.chunk_id for item in bm25_results],
            top_k=request.top_k,
        )
        # The source schemas are canonical.  Prefer Dense only as a stable
        # materialisation tie-breaker; the returned score is never RRF's score.
        by_chunk = {item.chunk_id: item for item in bm25_results}
        by_chunk.update({item.chunk_id: item for item in dense_results})
        results = [by_chunk[item.chunk_id].model_copy(update={"rank": rank}) for rank, item in enumerate(fused, start=1)]
        limitations: list[str] = []
        if dense_failure is not None:
            limitations.append("Dense retrieval was unavailable; BM25 candidates were used.")
        if bm25_failure is not None:
            limitations.append("BM25 retrieval was unavailable; Dense candidates were used.")
        if not results:
            limitations.append("No knowledge chunks matched the requested filters.")
        response = dense_response or bm25_response
        assert response is not None
        return KnowledgeRetrievalResponse(
            query=request.query,
            results=results,
            limitations=sorted(set(limitations)),
            index_id="hybrid-rrf",
            corpus_root_hash=response.corpus_root_hash,
        )
