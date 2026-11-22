"""Bounded ASGI admission; no raw forwarding headers or request-body logs."""
import asyncio
from contextlib import suppress
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from planner_core.config import get_settings
from server.common.exceptions import AppError, TooManyRequestsError
from server.security import admission

logger = logging.getLogger(__name__)


def rejection(exc):
    headers = {'Cache-Control': 'no-store'}
    if isinstance(exc, TooManyRequestsError):
        headers['Retry-After'] = str(exc.retry_after)
    return JSONResponse({'code': exc.error_code or exc.status_code, 'message': exc.message},
        status_code=exc.status_code, headers=headers)


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        settings = get_settings()
        if scope['type'] != 'http' or not settings.security_controls_enabled:
            return await self.app(scope, receive, send)
        request = Request(scope, receive=receive)
        path = scope['path'].rstrip('/')
        # Liveness is intentionally independent of MySQL admission storage;
        # edge limits still apply. It does not imply database readiness.
        if path == '/api/health' and request.method in {'GET', 'HEAD'}:
            return await self.app(scope, receive, send)
        if not (path.startswith(('/api/', '/oauth/')) or path == '/mcp'):
            return await self.app(scope, receive, send)
        state = scope.setdefault('state', {})
        state['security_leases'] = []
        factory = admission.factory_for(request)
        source = admission.ip_subject(request)
        try:
            if path.startswith('/api/admin') and not admission.admin_ip_allowed(request, settings.security_admin_allowed_ips):
                return await JSONResponse({'code': 'ADMIN_SOURCE_DENIED', 'message': '当前网络不允许访问管理接口。'}, status_code=403)(scope, receive, send)
            entries = [('ip', source)]
            if path in {'/api/auth/login', '/oauth/authorize'} and request.method == 'POST':
                entries.append(('login_ip', source))
            if path == '/api/auth/register' and request.method == 'POST':
                entries.append(('register', source))
            if path.startswith('/oauth/'):
                entries.append(('oauth', source))
            await run_in_threadpool(admission.consume, factory, entries)
        except AppError as exc:
            return await rejection(exc)(scope, receive, send)
        maximum = min(settings.security_request_max_bytes, 65536) if path.startswith(('/oauth/', '/api/auth/')) else settings.security_request_max_bytes
        length = request.headers.get('content-length')
        if length is not None:
            try:
                if int(length) < 0 or int(length) > maximum:
                    raise ValueError()
            except ValueError:
                return await JSONResponse({'code': 'REQUEST_TOO_LARGE', 'message': '请求内容过大或长度无效。'}, status_code=413)(scope, receive, send)
        # Bound before FastAPI parses JSON/multipart (it otherwise translates
        # receive exceptions into a generic parse error). Never read GET/SSE.
        replay_body = None
        if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            chunks, consumed = [], 0
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                chunk = message.get('body', b'')
                consumed += len(chunk)
                if consumed > maximum:
                    return await JSONResponse({'code': 'REQUEST_TOO_LARGE', 'message': '请求内容超过大小限制。'}, status_code=413)(scope, receive, send)
                chunks.append(chunk)
                if not message.get('more_body', False):
                    break
            replay_body = b''.join(chunks)
        async def bounded_receive():
            nonlocal replay_body
            if replay_body is not None:
                body, replay_body = replay_body, None
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()
        async def safe_send(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers', []))
                names = {key.lower() for key, _ in headers}
                for key, value in [(b'x-content-type-options', b'nosniff'), (b'referrer-policy', b'same-origin'),
                    (b'cache-control', b'no-store'), (b'x-frame-options', b'DENY')]:
                    if key not in names:
                        headers.append((key, value))
                message = {**message, 'headers': headers}
            await send(message)
        async def heartbeat():
            while True:
                await asyncio.sleep(settings.security_lease_seconds/3)
                try:
                    await run_in_threadpool(admission.renew, factory, list(state['security_leases']))
                except Exception:
                    logger.warning('security_lease_renewal_failed')
        task = asyncio.create_task(heartbeat())
        try:
            await self.app(scope, bounded_receive, safe_send)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            try:
                await asyncio.shield(run_in_threadpool(admission.release, factory, list(state['security_leases'])))
            except Exception:
                logger.warning('security_lease_release_failed')
