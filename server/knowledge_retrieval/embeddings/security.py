from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from server.knowledge_retrieval.errors import (
    KnowledgeEmbeddingConfigurationError,
)


_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.azure.internal",
    "169.254.169.254",
}


def validate_embedding_base_url(
    base_url: str,
    *,
    allow_local_development: bool = False,
) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise KnowledgeEmbeddingConfigurationError(
            "Embedding base URL must use HTTP or HTTPS."
        )
    if parsed.username is not None or parsed.password is not None:
        raise KnowledgeEmbeddingConfigurationError(
            "Embedding base URL must not contain credentials."
        )
    if parsed.query or parsed.fragment:
        raise KnowledgeEmbeddingConfigurationError(
            "Embedding base URL must not contain a query or fragment."
        )
    host = parsed.hostname.rstrip(".").lower()
    blocked = host in _BLOCKED_HOSTS or host.endswith(".localhost")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        blocked = blocked or any(
            (
                address.is_private,
                address.is_loopback,
                address.is_link_local,
                address.is_reserved,
                address.is_multicast,
                address.is_unspecified,
            )
        )
    if blocked and not allow_local_development:
        raise KnowledgeEmbeddingConfigurationError(
            "Embedding base URL host is not allowed."
        )
    return base_url.rstrip("/")
