import pytest
from pydantic import ValidationError

from server.common.exceptions import BadRequestError, ServiceUnavailableError
from server.schemas.weekly_review import WeeklyReviewAIOutput
from server.services.ai_plan_service import load_ai_json, normalize_ai_generation_exception


def valid_output():
    return {
        "summary": "本周执行稳定。",
        "positive_points": ["完成了关键课"],
        "attention_points": ["继续记录恢复数据"],
        "training_status": "normal",
        "status_explanation": "现有记录未显示组合异常信号。",
        "next_week_strategy": "保持原有结构。",
        "adjustments": [
            {
                "planned_workout_id": 123,
                "action": "reduce",
                "suggested_content": "轻松跑 8km",
                "suggested_distance_km": 8,
                "suggested_main_type": "easy",
                "suggested_target_pace_text": "4:40-5:00/km",
                "reason": "控制下一周总负荷",
            }
        ],
        "risk_notes": ["疼痛加重时停止强度训练并寻求专业评估"],
    }


def test_valid_weekly_review_json_passes():
    assert WeeklyReviewAIOutput.model_validate(valid_output()).adjustments[0].action.value == "reduce"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda body: body.pop("summary"),
        lambda body: body["adjustments"][0].update(action="increase"),
        lambda body: body["adjustments"][0].update(suggested_main_type="magic"),
        lambda body: body["adjustments"][0].update(suggested_distance_km=-1),
    ],
)
def test_invalid_weekly_review_output_fails(mutator):
    body = valid_output()
    mutator(body)
    with pytest.raises(ValidationError):
        WeeklyReviewAIOutput.model_validate(body)


def test_markdown_wrapped_json_follows_existing_cleaning_policy():
    assert load_ai_json('```json\n{"ok": true}\n```') == {"ok": True}
    with pytest.raises(BadRequestError):
        load_ai_json("```not valid")


def test_timeout_is_normalized_without_exposing_stack():
    error = normalize_ai_generation_exception(TimeoutError("request timed out"))
    assert isinstance(error, ServiceUnavailableError)
    assert "超时" in error.message
