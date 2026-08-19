"""Internal-only optional persistence for raw Provider reasoning."""

from __future__ import annotations

from sqlalchemy.orm import Session

from planner_core.database.models import ProviderReasoningRecord
from server.model_tasks import TaskModelProfile
from server.structured_task_provider import StructuredTaskResult


def persist_reasoning(
    db: Session,
    *,
    user_id: int,
    provider: str,
    profile: TaskModelProfile,
    result: StructuredTaskResult,
    related_record_type: str | None = None,
    related_record_id: int | None = None,
) -> ProviderReasoningRecord | None:
    if not profile.persist_reasoning or not result.reasoning_content:
        return None
    record = ProviderReasoningRecord(
        user_id=user_id,
        task_type=profile.task_type.value,
        provider=provider,
        model_name=profile.model,
        reasoning_content=result.reasoning_content,
        reasoning_token_count=result.reasoning_tokens,
        content_token_count=result.completion_tokens,
        finish_reason=result.finish_reason,
        related_record_type=related_record_type,
        related_record_id=related_record_id,
    )
    db.add(record)
    db.flush()
    return record
