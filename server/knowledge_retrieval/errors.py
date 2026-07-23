from __future__ import annotations


class KnowledgeCorpusError(ValueError):
    """Base error with a safe, repository-relative message."""


class KnowledgePathError(KnowledgeCorpusError):
    """The requested path escapes or violates the configured corpus root."""


class KnowledgeLoadError(KnowledgeCorpusError):
    """A source or document could not be loaded safely."""


class KnowledgeValidationError(KnowledgeCorpusError):
    """Corpus content is structurally invalid."""


class KnowledgeBuildError(KnowledgeCorpusError):
    """A derived manifest could not be published safely."""


class KnowledgeNotFoundError(KnowledgeCorpusError):
    """A requested document or chunk does not exist."""
