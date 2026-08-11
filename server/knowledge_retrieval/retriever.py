from __future__ import annotations

from server.knowledge_retrieval.embeddings.base import EmbeddingProvider
from server.knowledge_retrieval.errors import KnowledgeRetrievalError
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.manifest import load_manifest
from server.knowledge_retrieval.retrieval_schemas import (
    MAX_EXCERPT_CHARS,
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
    KnowledgeRetrievalResult,
)
from server.knowledge_retrieval.retrieval_validator import (
    validate_retrieval_binding,
)
from server.knowledge_retrieval.vector_stores.factory import (
    create_vector_store,
    vector_store_name,
)
from server.observability.tracing import active_trace_handle, active_tracer


class TrainingKnowledgeRetriever:
    def __init__(
        self,
        *,
        index_service: KnowledgeIndexService,
        provider: EmbeddingProvider,
        index_id: str | None = None,
        vector_store: str = "exact",
        qdrant_url: str | None = None,
        qdrant_api_key: str | None = None,
        qdrant_collection_prefix: str = "gaitlogic",
    ) -> None:
        self.index_service = index_service
        self.provider = provider
        self.index_id = index_id or index_service.latest_index_id()
        self.vector_store = vector_store
        self.qdrant_url, self.qdrant_api_key = qdrant_url, qdrant_api_key
        self.qdrant_collection_prefix = qdrant_collection_prefix

    def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
    ) -> KnowledgeRetrievalResponse:
        corpus = load_manifest(self.index_service.corpus_manifest_path)
        manifest = self.index_service.validate(self.index_id)
        validate_retrieval_binding(
            manifest,
            self.provider,
            corpus_root_hash=corpus.root_hash,
        )
        if vector_store_name(self.vector_store) != manifest.vector_store:
            raise KnowledgeRetrievalError(
                "Configured vector store does not match the selected index."
            )
        query_embedding = self.provider.embed_query(request.query)
        if query_embedding.dimensions != manifest.embedding_dimensions:
            raise KnowledgeRetrievalError(
                "Query embedding dimensions do not match the index."
            )
        store = create_vector_store(
            kind=manifest.vector_store,
            directory=self.index_service.index_root / self.index_id,
            index_id=self.index_id,
            dimensions=manifest.embedding_dimensions,
            qdrant_url=self.qdrant_url,
            qdrant_api_key=self.qdrant_api_key,
            qdrant_prefix=self.qdrant_collection_prefix,
        )
        tracer = active_tracer()
        handle = active_trace_handle()
        try:
            if tracer is None or handle is None:
                matches = store.search(
                    query_embedding.vector,
                    top_k=request.top_k,
                    filters=request.filters(),
                )
            else:
                with tracer.span(
                    handle,
                    component="knowledge",
                    operation="vector_search",
                    metadata={
                        "vector_store": manifest.vector_store,
                        "index_id": manifest.index_id,
                    },
                ) as span:
                    matches = store.search(
                        query_embedding.vector,
                        top_k=request.top_k,
                        filters=request.filters(),
                    )
                    span.add_metadata(result_count=len(matches))
        finally:
            store.close()
            self.provider.close()
        if request.min_score is not None:
            matches = [
                match for match in matches if match.score >= request.min_score
            ]
        chunks = {chunk.chunk_id: chunk for chunk in corpus.chunks}
        documents = {item.document_id: item for item in corpus.documents}
        sources = {item.source_id: item for item in corpus.sources}
        results: list[KnowledgeRetrievalResult] = []
        for rank, match in enumerate(matches, start=1):
            chunk = chunks.get(match.chunk_id)
            if chunk is None:
                raise KnowledgeRetrievalError(
                    "Index references a missing corpus chunk."
                )
            document = documents[chunk.document_id]
            source = sources[chunk.source_id]
            excerpt = chunk.content[:MAX_EXCERPT_CHARS]
            results.append(
                KnowledgeRetrievalResult(
                    rank=rank,
                    score=match.score,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    section=chunk.section,
                    excerpt=excerpt,
                    category=chunk.category,
                    tags=chunk.tags,
                    source_id=chunk.source_id,
                    source_title=source.title,
                    knowledge_version=chunk.knowledge_version,
                    evidence_level=chunk.metadata.evidence_level,
                    relative_path=document.relative_path,
                    limitations=[],
                )
            )
        limitations = list(query_embedding.warnings)
        if not results:
            limitations.append("No knowledge chunks matched the requested filters.")
        return KnowledgeRetrievalResponse(
            query=request.query,
            results=results,
            limitations=sorted(set(limitations)),
            index_id=manifest.index_id,
            corpus_root_hash=manifest.corpus_root_hash,
        )
