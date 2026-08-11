"""Internal deterministic identity material for checkpoint-write persistence."""

from __future__ import annotations

import hashlib


TASK_PATH_HASH_BYTES = 32


def compute_task_path_hash(task_path: str) -> bytes:
    """Return the SHA-256 digest of an exact UTF-8 task path.

    The digest narrows a MySQL composite index while the complete path remains
    stored for workflow semantics, auditability, and a final equality check.
    ``None`` is deliberately rejected instead of being rewritten to an empty
    path; the checkpoint-write column has always been non-nullable.
    """

    if not isinstance(task_path, str):
        raise TypeError("task_path must be a string")
    digest = hashlib.sha256(task_path.encode("utf-8")).digest()
    assert len(digest) == TASK_PATH_HASH_BYTES
    return digest
