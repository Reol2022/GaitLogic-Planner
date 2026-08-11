"""Trusted execution context for local MCP calls.

The stdio protocol does not establish a GaitLogic login in v0.15-A.  A host or
future authenticated transport must inject this context server-side; it is never
derived from tool arguments.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy.orm import Session

from server.observability.tracing import NOOP_TRACER, SafeTracer


SessionFactory = Callable[[], Session]
IdentityProvider = Callable[[], "McpRequestIdentity | None"]
_ACTIVE_IDENTITY: ContextVar["McpRequestIdentity | None"] = ContextVar(
    "active_mcp_identity", default=None
)


@dataclass(frozen=True)
class McpRequestIdentity:
    """Server-injected identity; never exposed in an MCP schema or trace."""

    user_id: int

    def __post_init__(self) -> None:
        if self.user_id <= 0:
            raise ValueError("MCP_IDENTITY_INVALID")


def get_active_mcp_identity() -> McpRequestIdentity | None:
    """Return request-scoped identity injected only by a trusted transport."""

    return _ACTIVE_IDENTITY.get()


@contextmanager
def activate_mcp_identity(identity: McpRequestIdentity) -> Iterator[None]:
    """Keep remote identity scoped to the current HTTP MCP request."""

    token = _ACTIVE_IDENTITY.set(identity)
    try:
        yield
    finally:
        _ACTIVE_IDENTITY.reset(token)


@dataclass(frozen=True)
class McpExecutionContext:
    """Dependencies supplied by a trusted local host or test harness."""

    identity_provider: IdentityProvider
    session_factory: SessionFactory | None = None
    tracer: SafeTracer = NOOP_TRACER
    transport: str = "stdio"

    @classmethod
    def unauthenticated_stdio(cls) -> "McpExecutionContext":
        """Build the safe v0.15-A command-line default.

        It intentionally has no identity and no database session factory, so a
        directly launched local server can list tools but cannot read a user's
        information before v0.15-B authentication exists.
        """

        return cls(identity_provider=lambda: None)
