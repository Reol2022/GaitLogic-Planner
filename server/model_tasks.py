"""Task-level model policy shared by Coach and planning workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from planner_core.config import Settings


class ModelTaskType(str, Enum):
    COACH_FACT_QUERY = "COACH_FACT_QUERY"
    COACH_ANALYSIS = "COACH_ANALYSIS"
    WEEKLY_REVIEW_ANALYSIS = "WEEKLY_REVIEW_ANALYSIS"
    PLAN_DESIGN = "PLAN_DESIGN"
    AI_PLAN_GENERATION = "AI_PLAN_GENERATION"


@dataclass(frozen=True)
class TaskModelProfile:
    task_type: ModelTaskType
    model: str
    thinking_enabled: bool
    max_output_tokens: int
    request_timeout_seconds: float
    response_format: Literal["json_schema", "json_object"]
    max_retries: int
    retry_token_multiplier: float
    persist_reasoning: bool = False

    def tokens_for_attempt(self, attempt: int) -> int:
        return min(65536, int(self.max_output_tokens * (self.retry_token_multiplier**attempt)))


def task_model_profile(settings: Settings, task_type: ModelTaskType) -> TaskModelProfile:
    common = {
        "response_format": settings.coach_agent_response_format_mode,
        "max_retries": settings.provider_task_max_retries,
        "retry_token_multiplier": settings.provider_task_retry_token_multiplier,
    }
    if task_type == ModelTaskType.COACH_FACT_QUERY:
        return TaskModelProfile(
            task_type=task_type,
            model=settings.coach_fact_query_model or settings.coach_agent_model,
            thinking_enabled=False,
            max_output_tokens=settings.coach_fact_query_max_output_tokens,
            request_timeout_seconds=settings.coach_agent_total_timeout_seconds,
            **common,
        )
    if task_type == ModelTaskType.COACH_ANALYSIS:
        return TaskModelProfile(
            task_type=task_type,
            model=settings.coach_analysis_model or settings.coach_agent_model,
            thinking_enabled=True,
            max_output_tokens=settings.coach_analysis_max_output_tokens,
            request_timeout_seconds=settings.coach_agent_total_timeout_seconds,
            **common,
        )
    if task_type == ModelTaskType.WEEKLY_REVIEW_ANALYSIS:
        return TaskModelProfile(
            task_type=task_type,
            model=settings.weekly_review_model or settings.deepseek_model,
            thinking_enabled=True,
            max_output_tokens=settings.weekly_review_max_output_tokens,
            request_timeout_seconds=settings.weekly_review_timeout_seconds,
            persist_reasoning=settings.weekly_reasoning_persistence_enabled,
            **common,
        )
    if task_type == ModelTaskType.PLAN_DESIGN:
        return TaskModelProfile(
            task_type=task_type,
            model=settings.plan_design_model or settings.deepseek_model,
            thinking_enabled=True,
            max_output_tokens=settings.plan_design_max_output_tokens,
            request_timeout_seconds=settings.plan_design_timeout_seconds,
            persist_reasoning=settings.plan_design_reasoning_persistence_enabled,
            **common,
        )
    return TaskModelProfile(
        task_type=task_type,
        model=settings.ai_plan_generation_model or settings.deepseek_model,
        thinking_enabled=True,
        max_output_tokens=settings.ai_plan_generation_max_output_tokens,
        request_timeout_seconds=settings.deepseek_timeout_seconds,
        **common,
    )
