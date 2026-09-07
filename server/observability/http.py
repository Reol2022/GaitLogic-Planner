"""FastAPI integration that creates a safe root trace for each HTTP request."""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response

from server.observability.tracing import SafeTracer


async def trace_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    *,
    tracer: SafeTracer,
) -> Response:
    """Trace method/status only; never retain path parameters, headers or body."""

    if not tracer.enabled:
        return await call_next(request)
    with tracer.request(
        component="http",
        operation="request",
        metadata={"transport": "http", "http_method": request.method},
    ) as handle:
        request.state.gaitlogic_trace_id = handle.trace_id
        response = await call_next(request)
        # Trace IDs are random correlation identifiers, not user data.  They
        # allow a caller to correlate a safe support log without exposing spans.
        response.headers["X-GaitLogic-Trace-Id"] = handle.trace_id
        return response
