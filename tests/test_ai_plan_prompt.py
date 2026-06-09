from datetime import date

from planner_core.enums import AIPlanIntensityStyle, RaceDistance
from server.schemas.ai_plan import AIPlanGenerateRequest
from server.services.ai_plan_prompt import build_prompt


def make_request() -> AIPlanGenerateRequest:
    return AIPlanGenerateRequest(
        runner_level="advanced",
        recent_pb_distance=RaceDistance.m5000,
        recent_pb_result="16:24",
        current_weekly_mileage_km=80,
        recent_4w_avg_mileage_km=76,
        available_training_days_per_week=6,
        can_double_run=False,
        fixed_rest_days=["周一"],
        injury_notes="无",
        training_preferences="二四日结构",
        target_race_name="眉山东坡半马",
        target_race_date=date(2026, 11, 8),
        target_distance=RaceDistance.half_marathon,
        target_result="1:11:30",
        plan_start_date=date(2026, 6, 1),
        plan_weeks=8,
        intensity_style=AIPlanIntensityStyle.standard,
        include_pace_guidance=True,
    )


def test_prompt_requires_json_output() -> None:
    prompt = build_prompt(make_request())
    assert "输出必须是合法 JSON" in prompt
    assert "不要输出 Markdown" in prompt
    assert '"weeks"' in prompt


def test_prompt_contains_safe_training_rules() -> None:
    prompt = build_prompt(make_request())
    assert "每周关键课不超过 2 次" in prompt
    assert "不安排连续两天高强度" in prompt
    assert "有伤痛时降低强度" in prompt
    assert "不提供医疗诊断" in prompt


def test_prompt_does_not_contain_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-api-key")
    prompt = build_prompt(make_request())
    assert "secret-api-key" not in prompt
