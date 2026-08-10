"""Stable, public-safe MCP failure categories."""

from __future__ import annotations

from enum import Enum


class McpErrorCode(str, Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    AUTH_CONTEXT_MISSING = "AUTH_CONTEXT_MISSING"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    INTERNAL_SAFE_ERROR = "INTERNAL_SAFE_ERROR"


class McpSafeError(Exception):
    """Internal control-flow exception carrying no unsafe diagnostic detail."""

    def __init__(self, code: McpErrorCode) -> None:
        super().__init__(code.value)
        self.code = code

