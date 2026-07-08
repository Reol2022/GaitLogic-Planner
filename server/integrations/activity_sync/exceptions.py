from __future__ import annotations

from server.common.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError


class ProviderNotFoundError(NotFoundError):
    def __init__(self, provider_key: str) -> None:
        super().__init__("未找到该运动数据同步平台。", error_code="PROVIDER_NOT_FOUND")
        self.provider_key = provider_key


class ProviderCapabilityNotSupportedError(BadRequestError):
    def __init__(self, capability: str) -> None:
        super().__init__("当前平台不支持该同步能力。", error_code="PROVIDER_CAPABILITY_NOT_SUPPORTED")
        self.capability = capability


class ProviderUnavailableError(ServiceUnavailableError):
    def __init__(self, message: str = "当前平台暂不可用，请稍后再试。", error_code: str = "PROVIDER_UNAVAILABLE") -> None:
        super().__init__(message, error_code=error_code)
