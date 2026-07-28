from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit


_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.azure.internal",
    "169.254.169.254",
}


def validate_provider_base_url(
    base_url: str,
    *,
    allow_local_development: bool = False,
) -> str:
    """Reject URL forms that can turn the provider adapter into an SSRF proxy."""
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Provider base URL must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Provider base URL must not contain credentials.")
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
        raise ValueError("Provider base URL host is not allowed.")
    if parsed.query or parsed.fragment:
        raise ValueError(
            "Provider base URL must not contain a query or fragment."
        )
    return base_url.rstrip("/")
