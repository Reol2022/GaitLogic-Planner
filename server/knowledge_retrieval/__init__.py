"""Deterministic training knowledge corpus foundation.

This package owns repository knowledge loading, validation, chunking, and
manifest generation. It intentionally has no dependency on ``server.agent``.
"""

from server.knowledge_retrieval.corpus_service import KnowledgeCorpusService
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
    "KnowledgeDocument",
    "KnowledgeSource",
]
