from __future__ import annotations

import hashlib
import json
from typing import Any

from server.common.exceptions import BadRequestError


DEFAULT_MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024


def safe_filename(filename: str) -> str:
    return filename.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]


def payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def bytes_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_upload_basics(
    *,
    filename: str,
    content_type: str | None,
    content: bytes,
    supported_extensions: set[str],
    allowed_mime_types: dict[str, set[str]],
    max_file_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
) -> tuple[str, str]:
    if not content:
        raise BadRequestError("上传文件不能为空。")
    if len(content) > max_file_size_bytes:
        raise BadRequestError("文件过大，单次导入最大支持 2MB。")

    clean_name = safe_filename(filename)
    extension = "." + clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else ""
    if extension == ".xls":
        raise BadRequestError("暂不支持 .xls，请另存为 .xlsx 后再上传。")
    if extension not in supported_extensions:
        raise BadRequestError("不支持的文件格式。")

    normalized_mime = content_type.split(";")[0] if content_type else None
    if normalized_mime and normalized_mime not in allowed_mime_types[extension]:
        raise BadRequestError("文件 MIME 类型与扩展名不匹配。")
    return clean_name, extension
