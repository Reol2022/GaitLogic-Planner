from __future__ import annotations

from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.retrieval_schemas import MAX_EXCERPT_CHARS, KnowledgeRetrievalRequest, KnowledgeRetrievalResponse, KnowledgeRetrievalResult
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.observability.tracing import active_trace_handle, active_tracer


class TrainingKnowledgeBm25Retriever:
    """Public-schema sparse retriever; no embedding provider is involved."""

    def __init__(self, *, index_service: Bm25IndexService, index_id: str | None = None) -> None:
        self.index_service = index_service
        self.index_id = index_id or index_service.latest_index_id()

    def retrieve(self, request: KnowledgeRetrievalRequest) -> KnowledgeRetrievalResponse:
        corpus = load_manifest(self.index_service.corpus_manifest_path)
        manifest = self.index_service.validate(self.index_id)
        _, index = self.index_service.load(self.index_id)
        tracer, handle = active_tracer(), active_trace_handle()
        def search():
            return index.search(
                request.query, top_k=request.top_k,
                categories={item.value for item in request.categories},
                tags=set(request.tags), language=request.language,
            )
        if tracer is None or handle is None:
            matches = search()
        else:
            with tracer.span(handle, component="knowledge", operation="sparse_search", metadata={"retrieval_strategy": "bm25", "index_id": manifest.index_id}) as span:
                matches = search()
                span.add_metadata(result_count=len(matches))
        chunks = {item.chunk_id: item for item in corpus.chunks}
        documents = {item.document_id: item for item in corpus.documents}
        sources = {item.source_id: item for item in corpus.sources}
        results: list[KnowledgeRetrievalResult] = []
        for rank, (match, score) in enumerate(matches, start=1):
            chunk = chunks.get(match.chunk_id)
            if chunk is None:
                raise KnowledgeRetrievalError("BM25 index references a missing corpus chunk.")
            document, source = documents[chunk.document_id], sources[chunk.source_id]
            # Public retrieval results historically use a bounded score.  BM25 is
            # unbounded, so expose only its monotonic bounded projection; raw
            # scores remain process-local and are never part of the API contract.
            bounded_score = score / (1.0 + score)
            results.append(KnowledgeRetrievalResult(rank=rank, score=round(bounded_score, 8), chunk_id=chunk.chunk_id, document_id=chunk.document_id, title=chunk.title, section=chunk.section, excerpt=chunk.content[:MAX_EXCERPT_CHARS], category=chunk.category, tags=chunk.tags, source_id=chunk.source_id, source_title=source.title, knowledge_version=chunk.knowledge_version, evidence_level=chunk.metadata.evidence_level, relative_path=document.relative_path, limitations=[]))
        limitations = [] if results else ["No knowledge chunks matched the requested filters."]
        return KnowledgeRetrievalResponse(query=request.query, results=results, limitations=limitations, index_id=manifest.index_id, corpus_root_hash=manifest.corpus_root_hash)
