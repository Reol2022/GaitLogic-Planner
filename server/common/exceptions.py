import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, SQLAlchemyError

logger = logging.getLogger(__name__)


def _error_response(
    status_code: int,
    code: int | str,
    message: str,
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    content: dict[str, Any] = {"code": code, "message": message}
    content.update(extra)
    return JSONResponse(status_code=status_code, content=content, headers=headers)


class AppError(Exception):
    status_code = 400
    error_code: int | str | None = None

    def __init__(self, message: str, error_code: int | str | None = None) -> None:
        self.message = message
        self.error_code = error_code


class BadRequestError(AppError):
    status_code = 400


class NotFoundError(AppError):
    status_code = 404


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class ConflictError(AppError):
    status_code = 409


class TooManyRequestsError(AppError):
    status_code = 429

    def __init__(self, message: str, error_code=None, *, retry_after: int = 60):
        super().__init__(message, error_code)
        self.retry_after = max(1, retry_after)


class ServiceUnavailableError(AppError):
    status_code = 503


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    headers = {'Retry-After': str(exc.retry_after), 'Cache-Control': 'no-store'} if isinstance(exc, TooManyRequestsError) else None
    return _error_response(exc.status_code, exc.error_code or exc.status_code, exc.message, headers=headers)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else "请求处理失败。"
    return _error_response(exc.status_code, exc.status_code, message, headers=exc.headers)


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return _error_response(
        400,
        "VALIDATION_ERROR",
        "请求参数不正确，请检查填写内容。",
        detail=[{'loc': list(item['loc']), 'type': item['type']} for item in exc.errors()],
    )


async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    logger.warning("Database constraint violation on %s %s", request.method, request.url.path)
    return _error_response(
        400,
        "DATABASE_CONSTRAINT_VIOLATION",
        "数据保存失败，可能存在重复记录或关联数据不正确。",
    )


async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database error method=%s route=%s exception_type=%s", request.method,
        getattr(request.scope.get('route'), 'path', '<unmatched>'), type(exc).__name__)
    if isinstance(exc, OperationalError) or (
        isinstance(exc, DBAPIError) and exc.connection_invalidated
    ):
        return _error_response(
            503,
            "DATABASE_CONNECTION_ERROR",
            "数据库连接失败，请稍后重试或联系管理员。",
        )
    return _error_response(
        500,
        "DATABASE_ERROR",
        "数据库服务异常，请稍后重试。",
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error method=%s route=%s exception_type=%s", request.method,
        getattr(request.scope.get('route'), 'path', '<unmatched>'), type(exc).__name__)
    return _error_response(
        500,
        "INTERNAL_SERVER_ERROR",
        "服务器处理请求时发生异常，请稍后重试。",
    )
