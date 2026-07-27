"""Deterministic training knowledge corpus foundation.

This package owns repository knowledge loading, validation, chunking, and
manifest generation. It intentionally has no dependency on ``server.agent``.
"""

from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
from server.knowledge_retrieval.index_service import KnowledgeIndexService
from server.knowledge_retrieval.retrieval_schemas import (
    KnowledgeRetrievalRequest,
    KnowledgeRetrievalResponse,
)
from server.knowledge_retrieval.retriever import TrainingKnowledgeRetriever
from server.knowledge_retrieval.schemas import (
    CorpusManifest,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeSource,
)

__all__ = [
    "CorpusManifest",
    "KnowledgeChunk",
    "KnowledgeCorpusService",
    "KnowledgeIndexService",
    "KnowledgeDocument",
    "KnowledgeSource",
    "KnowledgeRetrievalRequest",
    "KnowledgeRetrievalResponse",
    "TrainingKnowledgeRetriever",
]
