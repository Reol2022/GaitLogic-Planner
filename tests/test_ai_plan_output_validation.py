import pytest

from server.common.exceptions import BadRequestError
from server.services.ai_plan_service import validate_ai_output


def valid_output() -> dict:
    return {
        "title": "8 周半马计划",
        "goal": "半马 1:11:30",
        "start_date": "2026-06-01",
        "end_date": "2026-07-26",
        "target_race_name": "测试半马",
        "target_race_date": "2026-08-01",
        "target_result": "1:11:30",
        "summary": "稳步推进",
        "risk_notes": ["注意恢复"],
        "weeks": [
            {
                "block_name": "Week 1",
                "phase_name": "基础期",
                "focus": "恢复接量",
                "planned_distance_km": 80,
                "workouts": [
                    {
                        "date": "2026-06-01",
                        "weekday": "周一",
                        "planned_content": "轻松跑 10km",
                        "focus_note": "控制心率",
                        "planned_distance_km": 10,
                        "main_type": "E",
                        "target_pace_text": "4:40-5:20/km",
                    }
                ],
            }
        ],
    }


def test_valid_json_passes() -> None:
    data = validate_ai_output(valid_output())
    assert data["title"] == "8 周半马计划"


def test_missing_weeks_fails() -> None:
    data = valid_output()
    data.pop("weeks")
    with pytest.raises(BadRequestError):
        validate_ai_output(data)


def test_workout_date_format_error_fails() -> None:
    data = valid_output()
    data["weeks"][0]["workouts"][0]["date"] = "2026/06/01"
    with pytest.raises(BadRequestError):
        validate_ai_output(data)


def test_planned_distance_non_numeric_fails() -> None:
    data = valid_output()
    data["weeks"][0]["workouts"][0]["planned_distance_km"] = "ten"
    with pytest.raises(BadRequestError):
        validate_ai_output(data)
