"""Task-level model policy shared by Coach and planning workflows."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from planner_core.config import Settings


class ModelTaskType(str, Enum):
    COACH_CHAT_FAST = "COACH_CHAT_FAST"
    COACH_FACT_QUERY = "COACH_FACT_QUERY"
    COACH_ANALYSIS = "COACH_ANALYSIS"
    WEEKLY_REVIEW_ANALYSIS = "WEEKLY_REVIEW_ANALYSIS"
    PLAN_DESIGN = "PLAN_DESIGN"
    AI_PLAN_GENERATION = "AI_PLAN_GENERATION"


@dataclass(frozen=True)
class TaskModelProfile:
    profile_name: Literal["chat_fast", "coach_facts", "coach_analysis", "plan_reasoning"]
    task_type: ModelTaskType
    model: str
    thinking_enabled: bool
    reasoning_effort: Literal["low", "high", "max"] | None
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
    if task_type == ModelTaskType.COACH_CHAT_FAST:
        return TaskModelProfile(
            profile_name="chat_fast",
            task_type=task_type,
            model=settings.coach_chat_fast_model or settings.coach_agent_model,
            thinking_enabled=False,
            reasoning_effort=None,
            max_output_tokens=settings.coach_chat_fast_max_output_tokens,
            request_timeout_seconds=settings.coach_agent_total_timeout_seconds,
            **common,
        )
    if task_type == ModelTaskType.COACH_FACT_QUERY:
        return TaskModelProfile(
            profile_name="coach_facts",
            task_type=task_type,
            model=settings.coach_fact_query_model or settings.coach_agent_model,
            thinking_enabled=False,
            reasoning_effort=None,
            max_output_tokens=settings.coach_fact_query_max_output_tokens,
            request_timeout_seconds=settings.coach_agent_total_timeout_seconds,
            **common,
        )
    if task_type == ModelTaskType.COACH_ANALYSIS:
        return TaskModelProfile(
            profile_name="coach_analysis",
            task_type=task_type,
            model=settings.coach_analysis_model or settings.coach_agent_model,
            # Coach responses are structured, bounded explanations.  Do not
            # silently enable DeepSeek thinking here: deployments control this
            # explicitly through COACH_AGENT_THINKING_MODE.  Keeping a
            # disabled deployment non-thinking prevents reasoning output from
            # consuming the response budget and destabilising final JSON.
            thinking_enabled=settings.coach_agent_thinking_mode != "disabled",
            reasoning_effort=settings.coach_analysis_reasoning_effort,
            max_output_tokens=settings.coach_analysis_max_output_tokens,
            request_timeout_seconds=settings.coach_agent_total_timeout_seconds,
            **common,
        )
    if task_type == ModelTaskType.WEEKLY_REVIEW_ANALYSIS:
        return TaskModelProfile(
            profile_name="coach_analysis",
            task_type=task_type,
            model=settings.weekly_review_model or settings.deepseek_model,
            # Weekly review is structured extraction plus deterministic rule
            # validation. Honour the deployment-wide Thinking policy so a
            # disabled setting also keeps these two long provider calls light.
            thinking_enabled=settings.coach_agent_thinking_mode != "disabled",
            reasoning_effort=settings.weekly_review_reasoning_effort,
            max_output_tokens=settings.weekly_review_max_output_tokens,
            request_timeout_seconds=settings.weekly_review_timeout_seconds,
            persist_reasoning=settings.weekly_reasoning_persistence_enabled,
            **common,
        )
    if task_type == ModelTaskType.PLAN_DESIGN:
        return TaskModelProfile(
            profile_name="plan_reasoning",
            task_type=task_type,
            model=settings.plan_design_model or settings.deepseek_model,
            thinking_enabled=settings.coach_agent_thinking_mode != "disabled",
            reasoning_effort=settings.plan_design_reasoning_effort,
            max_output_tokens=settings.plan_design_max_output_tokens,
            request_timeout_seconds=settings.plan_design_timeout_seconds,
            persist_reasoning=settings.plan_design_reasoning_persistence_enabled,
            **common,
        )
    return TaskModelProfile(
        profile_name="plan_reasoning",
        task_type=task_type,
        model=settings.ai_plan_generation_model or settings.deepseek_model,
        # Generating a complete, structured multi-week plan already produces
        # a large response.  Keep this request non-thinking so hidden
        # reasoning cannot exhaust the response window or trigger retries.
        thinking_enabled=False,
        reasoning_effort=None,
        max_output_tokens=settings.ai_plan_generation_max_output_tokens,
        request_timeout_seconds=settings.deepseek_timeout_seconds,
        **common,
    )


def coach_intent_model_profile(settings: Settings, intent: object) -> TaskModelProfile:
    """Resolve a server-owned Coach execution profile from its classified task."""

    value = str(getattr(intent, "value", intent))
    if value in {"CASUAL_CONVERSATION", "COACH_CAPABILITY_QUERY", "GENERAL_TRAINING_QUESTION"}:
        return task_model_profile(settings, ModelTaskType.COACH_CHAT_FAST)
    if value in {"PERSONAL_TRAINING_FACT_QUERY", "PERSONAL_TRAINING_STATUS"}:
        return task_model_profile(settings, ModelTaskType.COACH_FACT_QUERY)
    if value == "PLAN_ADJUSTMENT_ANALYSIS":
        return task_model_profile(settings, ModelTaskType.PLAN_DESIGN)
    return task_model_profile(settings, ModelTaskType.COACH_ANALYSIS)
