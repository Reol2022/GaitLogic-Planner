from __future__ import annotations

from server.knowledge_retrieval.errors import KnowledgeRetrievalError


class KnowledgeRerankerError(KnowledgeRetrievalError):
    """Safe failure from an external candidate reranker."""

    def __init__(self, message: str, *, category=None) -> None:
        super().__init__(message)
        self.category = category
