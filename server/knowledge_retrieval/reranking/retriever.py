"""Fixed-pool external reranking with safe Hybrid-RRF fallback."""

from __future__ import annotations

from typing import Protocol

from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.hybrid.fusion import ReciprocalRankFusion
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.reranking.base import RerankCandidate, Reranker
from server.knowledge_retrieval.retrieval_schemas import (
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
)
from server.observability.tracing import active_trace_handle, active_tracer


class _Retriever(Protocol):
    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse: ...


class RerankingKnowledgeRetriever:
    """Retrieve a bounded 8+8 union, then let a Provider order it.

    Provider failure never alters the factual retrieval boundary: the already
    computed Hybrid RRF order is returned with a safe limitation instead.
    """

    strategy_name = "rerank"
    candidate_depth = 8

    def __init__(self, *, dense_retriever: _Retriever, bm25_retriever: _Retriever, reranker: Reranker, corpus_manifest_path) -> None:
        self.dense_retriever = dense_retriever
        self.bm25_retriever = bm25_retriever
        self.reranker = reranker
        self.corpus_manifest_path = corpus_manifest_path
        self.fusion = ReciprocalRankFusion()

    @staticmethod
    def _response_or_none(retriever: _Retriever, request: KnowledgeRetrievalRequest):
        try:
            return retriever.retrieve(request), None
        except Exception as exc:
            return None, exc

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse:
        candidate_request = request.model_copy(update={"top_k": self.candidate_depth})
        dense, dense_error = self._response_or_none(self.dense_retriever, candidate_request)
        bm25, bm25_error = self._response_or_none(self.bm25_retriever, candidate_request)
        if dense is None and bm25 is None:
            raise KnowledgeRetrievalError("Rerank knowledge retrieval is unavailable.")
        dense_results = dense.results if dense else []
        bm25_results = bm25.results if bm25 else []
        if not dense_results and not bm25_results:
            response = dense or bm25
            assert response is not None
            return KnowledgeRetrievalResponse(
                query=request.query,
                results=[],
                limitations=["No knowledge chunks matched the requested filters."],
                index_id="rerank-siliconflow",
                corpus_root_hash=response.corpus_root_hash,
            )
        fused = self.fusion.fuse(
            dense_chunk_ids=[item.chunk_id for item in dense_results],
            bm25_chunk_ids=[item.chunk_id for item in bm25_results],
            top_k=len({item.chunk_id for item in dense_results + bm25_results}),
        )
        by_chunk = {item.chunk_id: item for item in bm25_results}
        by_chunk.update({item.chunk_id: item for item in dense_results})
        fallback_items = [by_chunk[item.chunk_id] for item in fused]
        corpus = load_manifest(self.corpus_manifest_path)
        content = {item.chunk_id: item.content for item in corpus.chunks}
        candidates = [RerankCandidate(chunk_id=item.chunk_id, text=content[item.chunk_id]) for item in fallback_items if item.chunk_id in content]
        if not candidates:
            return KnowledgeRetrievalResponse(
                query=request.query, results=[], limitations=["No knowledge chunks matched the requested filters."],
                index_id="rerank-siliconflow", corpus_root_hash=(dense or bm25).corpus_root_hash,
            )
        top_n = min(request.top_k, len(candidates))
        tracer, handle = active_tracer(), active_trace_handle()
        failure = None
        reranked = None
        def call() -> None:
            nonlocal reranked, failure
            try:
                reranked = self.reranker.rerank(query=request.query, candidates=candidates, top_n=top_n)
            except Exception as exc:
                failure = exc
        if tracer is None or handle is None:
            call()
        else:
            with tracer.span(handle, component="knowledge", operation="rerank", metadata={"retrieval_strategy": "rerank", "reranker": self.reranker.provider_kind, "model_family": self.reranker.model_family, "candidate_count": len(candidates), "top_n": top_n}) as span:
                with tracer.span(handle, component="provider", operation="rerank", metadata={"provider_kind": self.reranker.provider_kind, "model_family": self.reranker.model_family, "attempt": 1}) as provider_span:
                    call()
                    reliability = self.reranker.last_reliability
                    provider_span.add_metadata(attempt=reliability.attempts, failure_category=reliability.failure_category.value if reliability.failure_category else None)
                    if failure is not None:
                        provider_span.mark_error(reliability.failure_category.value if reliability.failure_category else "PROVIDER_UNKNOWN_ERROR")
                if failure is not None:
                    span.mark_fallback("RERANKER_UNAVAILABLE")
                    span.add_metadata(failure_category=getattr(getattr(self.reranker, "last_reliability", None), "failure_category", None).value if getattr(getattr(self.reranker, "last_reliability", None), "failure_category", None) else "PROVIDER_UNKNOWN_ERROR")
        limitations: list[str] = []
        if dense_error is not None:
            limitations.append("Dense retrieval was unavailable; BM25 candidates were used.")
        if bm25_error is not None:
            limitations.append("BM25 retrieval was unavailable; Dense candidates were used.")
        if failure is not None or reranked is None:
            ordered = fallback_items[:top_n]
            limitations.append("Reranker was unavailable; stable Hybrid RRF ordering was used.")
        else:
            ordered = [fallback_items[item.index] for item in reranked]
        return KnowledgeRetrievalResponse(
            query=request.query,
            results=[item.model_copy(update={"rank": rank}) for rank, item in enumerate(ordered, start=1)],
            limitations=sorted(set(limitations)),
            index_id="rerank-siliconflow",
            corpus_root_hash=(dense or bm25).corpus_root_hash,
        )
