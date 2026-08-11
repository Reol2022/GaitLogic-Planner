"""GaitLogic-authenticated Streamable HTTP transport for the read-only MCP server.

This is intentionally *not* an MCP OAuth 2.1 authorization-server
implementation. It validates short-lived, audience-bound GaitLogic MCP tokens
and injects the resulting identity into the existing MCP adapter.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from planner_core.config import Settings, get_settings
from planner_core.database.models import UserAccount
from planner_core.database.session import SessionLocal
from server.mcp.context import (
    McpExecutionContext,
    McpRequestIdentity,
    activate_mcp_identity,
    get_active_mcp_identity,
)
from server.mcp.errors import McpErrorCode
from server.mcp.adapters import KnowledgeToolFactory
from server.mcp.knowledge import McpKnowledgeResourceService
from server.mcp.server import create_mcp_server
from server.observability.factory import get_configured_tracer
from server.observability.tracing import SafeTracer
from server.services.auth_service import McpTokenValidationError, decode_mcp_access_token


logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
DependenciesFactory = Callable[[Session], object]


@dataclass(frozen=True)
class McpHttpDependencies:
    """Trusted HTTP transport dependencies; no client supplies these values."""

    settings: Settings
    session_factory: SessionFactory = SessionLocal
    tracer: SafeTracer | None = None
    dependencies_factory: DependenciesFactory | None = None
    knowledge_tool_factory: KnowledgeToolFactory | None = None
    knowledge_resource_service: McpKnowledgeResourceService | None = None

    @property
    def active_tracer(self) -> SafeTracer:
        return self.tracer or get_configured_tracer()


def _safe_error(status_code: int, code: McpErrorCode) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else {}
    return JSONResponse(status_code=status_code, content={"code": code.value}, headers=headers)


class McpHttpSecurityMiddleware:
    """Origin validation and Bearer identity injection outside the MCP protocol app."""

    def __init__(self, app: ASGIApp, dependencies: McpHttpDependencies) -> None:
        self.app = app
        self.dependencies = dependencies

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        tracer = self.dependencies.active_tracer
        handle = tracer.start_trace()
        with tracer.span(
            handle,
            component="mcp.http",
            operation="request",
            metadata={"transport": "streamable_http"},
            root=True,
        ) as root:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in self.dependencies.settings.mcp_allowed_origins_list:
                root.set_status("FAILED", error_code=McpErrorCode.INVALID_ORIGIN.value)
                root.add_metadata(status="FAILED", failure_category=McpErrorCode.INVALID_ORIGIN.value)
                await _safe_error(403, McpErrorCode.INVALID_ORIGIN)(scope, receive, send)
                return

            with tracer.span(
                handle,
                component="auth",
                operation="validate",
                metadata={"transport": "streamable_http"},
            ) as auth_span:
                identity, error = self._authenticate(request)
                if error is not None:
                    auth_span.set_status("FAILED", error_code=error.value)
                    auth_span.add_metadata(
                        auth_status="FAILED", status="FAILED", failure_category=error.value
                    )
                    root.set_status("FAILED", error_code=error.value)
                    root.add_metadata(status="FAILED", failure_category=error.value)
                    await _safe_error(401, error)(scope, receive, send)
                    return
                auth_span.add_metadata(auth_status="SUCCEEDED", status="SUCCEEDED")

            assert identity is not None
            with activate_mcp_identity(identity):
                await self.app(scope, receive, send)

    def _authenticate(self, request: Request) -> tuple[McpRequestIdentity | None, McpErrorCode | None]:
        authorization = request.headers.get("authorization")
        if authorization is None:
            return None, McpErrorCode.UNAUTHENTICATED
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token or token.strip() != token:
            return None, McpErrorCode.INVALID_TOKEN
        try:
            payload = decode_mcp_access_token(token)
        except McpTokenValidationError as exc:
            return None, McpErrorCode(exc.code)

        session: Session | None = None
        try:
            session = self.dependencies.session_factory()
            user = session.scalar(select(UserAccount).where(UserAccount.id == int(payload["sub"])))
            if user is None or user.status != "active":
                return None, McpErrorCode.INSUFFICIENT_PERMISSION
            return McpRequestIdentity(user_id=user.id), None
        except Exception:
            logger.warning("mcp_http_identity_lookup_failed code=MCP_HTTP_IDENTITY_LOOKUP_FAILED")
            return None, McpErrorCode.INTERNAL_SAFE_ERROR
        finally:
            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    logger.warning("mcp_http_auth_rollback_failed code=MCP_HTTP_AUTH_ROLLBACK_FAILED")
                finally:
                    session.close()


def create_mcp_http_app(
    *,
    dependencies: McpHttpDependencies | None = None,
    json_response: bool = True,
) -> ASGIApp:
    """Create SDK-owned Streamable HTTP with GaitLogic auth as an outer layer."""

    resolved = dependencies or McpHttpDependencies(settings=get_settings())
    context = McpExecutionContext(
        identity_provider=get_active_mcp_identity,
        session_factory=resolved.session_factory,
        tracer=resolved.active_tracer,
        transport="streamable_http",
    )
    server = create_mcp_server(
        context,
        dependencies_factory=resolved.dependencies_factory,
        knowledge_tool_factory=resolved.knowledge_tool_factory,
        knowledge_resource_service=resolved.knowledge_resource_service,
    )
    sdk_app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=json_response,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=resolved.settings.mcp_allowed_hosts_list,
            allowed_origins=resolved.settings.mcp_allowed_origins_list,
        ),
        host=resolved.settings.mcp_http_host,
    )
    return McpHttpSecurityMiddleware(sdk_app, resolved)
