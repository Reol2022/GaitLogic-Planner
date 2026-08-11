"""Deterministic sparse retrieval primitives.

The package deliberately has no Qdrant or embedding dependency.  A future
Qdrant sparse adapter can implement the same retrieval boundary without
changing callers or the public knowledge-result schema.
"""

from server.knowledge_retrieval.sparse.bm25 import BM25Analyzer, BM25Index
from server.knowledge_retrieval.sparse.index_service import Bm25IndexService
from server.knowledge_retrieval.sparse.retriever import TrainingKnowledgeBm25Retriever

__all__ = [
    "BM25Analyzer",
    "BM25Index",
    "Bm25IndexService",
    "TrainingKnowledgeBm25Retriever",
]
