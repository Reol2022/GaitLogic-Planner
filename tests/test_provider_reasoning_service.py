from types import SimpleNamespace

from planner_core.config import Settings
from server.model_tasks import ModelTaskType, task_model_profile
from server.services.provider_reasoning_service import persist_reasoning
from server.structured_task_provider import StructuredTaskResult
from server.weekly_review_graph.schemas import WeeklyReviewAnalysis


class Session:
    def __init__(self):
        self.added = []
        self.flushed = False

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flushed = True


def result():
    return StructuredTaskResult(
        value=WeeklyReviewAnalysis(
            overall_assessment="ok", execution_assessment="ok", load_assessment="ok",
            key_session_assessment="ok", recovery_assessment="ok", intensity_assessment="ok",
        ),
        reasoning_content="内部推理",
        finish_reason="stop",
        prompt_tokens=1,
        completion_tokens=2,
        reasoning_tokens=1,
        content_length=10,
        attempts=1,
        max_output_tokens=100,
    )


def test_weekly_reasoning_is_optional_and_coach_has_no_persistence_profile():
    enabled = Settings(_env_file=None, WEEKLY_REASONING_PERSISTENCE_ENABLED=True)
    session = Session()
    record = persist_reasoning(
        session,
        user_id=7,
        provider="fictional",
        profile=task_model_profile(enabled, ModelTaskType.WEEKLY_REVIEW_ANALYSIS),
        result=result(),
    )
    assert record is not None and record.reasoning_content == "内部推理"
    assert session.flushed
    disabled = Settings(_env_file=None, WEEKLY_REASONING_PERSISTENCE_ENABLED=False)
    assert persist_reasoning(
        Session(), user_id=7, provider="fictional",
        profile=task_model_profile(disabled, ModelTaskType.WEEKLY_REVIEW_ANALYSIS), result=result()
    ) is None
    assert task_model_profile(enabled, ModelTaskType.COACH_ANALYSIS).persist_reasoning is False
