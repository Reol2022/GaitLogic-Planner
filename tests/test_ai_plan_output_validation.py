import json

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
        "summary": "稳步推进，控制强度。",
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
                    },
                    {
                        "date": "2026-06-02",
                        "weekday": "周二",
                        "planned_content": "阈值跑 4x2km",
                        "focus_note": "可控阈值",
                        "planned_distance_km": 14,
                        "main_type": "T1",
                        "target_pace_text": "3:35-3:45/km",
                    },
                ],
            }
        ],
    }


def test_valid_json_passes() -> None:
    data = validate_ai_output(valid_output())
    assert data["title"] == "8 周半马计划"


def test_expected_plan_weeks_mismatch_fails() -> None:
    with pytest.raises(BadRequestError):
        validate_ai_output(valid_output(), expected_plan_weeks=2)


def test_expected_plan_weeks_match_passes() -> None:
    data = valid_output()
    data["weeks"].append(
        {
            "block_name": "Week 2",
            "phase_name": "基础期",
            "focus": "稳定跑量",
            "planned_distance_km": 82,
            "workouts": [
                {
                    "date": "2026-06-08",
                    "weekday": "周一",
                    "planned_content": "恢复跑 8km",
                    "focus_note": "吸收上一周训练",
                    "planned_distance_km": 8,
                    "main_type": "REC",
                    "target_pace_text": "",
                }
            ],
        }
    )
    assert len(validate_ai_output(data, expected_plan_weeks=2)["weeks"]) == 2


def test_markdown_wrapped_json_can_be_cleaned() -> None:
    data = validate_ai_output(f"```json\n{json.dumps(valid_output(), ensure_ascii=False)}\n```")
    assert data["weeks"][0]["block_name"] == "Week 1"


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
    data["weeks"][0]["workouts"][0]["planned_distance_km"] = "10km"
    with pytest.raises(BadRequestError):
        validate_ai_output(data)


def test_invalid_main_type_fails() -> None:
    data = valid_output()
    data["weeks"][0]["workouts"][0]["main_type"] = "FAST"
    with pytest.raises(BadRequestError):
        validate_ai_output(data)


def test_non_rest_workout_requires_focus_note() -> None:
    data = valid_output()
    data["weeks"][0]["workouts"][0]["focus_note"] = ""
    with pytest.raises(BadRequestError):
        validate_ai_output(data)


def test_consecutive_high_intensity_fails() -> None:
    data = valid_output()
    data["weeks"][0]["workouts"] = [
        {
            "date": "2026-06-02",
            "weekday": "周二",
            "planned_content": "阈值跑",
            "focus_note": "阈值能力",
            "planned_distance_km": 14,
            "main_type": "T1",
            "target_pace_text": "3:35-3:45/km",
        },
        {
            "date": "2026-06-03",
            "weekday": "周三",
            "planned_content": "间歇跑",
            "focus_note": "VO2max",
            "planned_distance_km": 12,
            "main_type": "I",
            "target_pace_text": "3:10-3:20/km",
        },
    ]
    with pytest.raises(BadRequestError):
        validate_ai_output(data)
