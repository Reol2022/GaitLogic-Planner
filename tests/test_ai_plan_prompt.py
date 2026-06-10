from datetime import date

from planner_core.enums import AIPlanIntensityStyle, RaceDistance
from server.schemas.ai_plan import AIPlanGenerateRequest
from server.services.ai_plan_prompt import (
    build_ai_plan_system_prompt,
    build_ai_plan_user_prompt,
    build_prompt,
)


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
        training_preferences="二四日结构，偏丹尼尔斯阈值训练，但希望控制伤病风险",
        target_race_name="眉山东坡半马",
        target_race_date=date(2026, 11, 8),
        target_distance=RaceDistance.half_marathon,
        target_result="1:11:30",
        plan_start_date=date(2026, 6, 1),
        plan_weeks=8,
        intensity_style=AIPlanIntensityStyle.standard,
        include_pace_guidance=True,
    )


def test_system_prompt_requires_json_output() -> None:
    prompt = build_ai_plan_system_prompt()
    assert "只输出 JSON" in prompt
    assert "不要输出 Markdown" in prompt
    assert '"weeks"' in prompt


def test_system_prompt_contains_professional_training_rules() -> None:
    prompt = build_ai_plan_system_prompt()
    assert "每周关键课不超过 2 次" in prompt
    assert "不安排连续两天高强度" in prompt
    assert "不是医生，不提供医疗诊断" in prompt
    assert "Jack Daniels" in prompt
    assert "挪威双阈值" in prompt
    assert "Renato Canova" in prompt


def test_system_prompt_does_not_contain_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-api-key")
    prompt = build_ai_plan_system_prompt()
    assert "secret-api-key" not in prompt


def test_user_prompt_contains_runner_goal_and_preferences() -> None:
    prompt = build_ai_plan_user_prompt(
        make_request(),
        {
            "preferred_training_systems": ["丹尼尔斯", "卡诺瓦专项"],
            "intensity_conservatism": "conservative",
            "key_workout_habit": "周二周四关键课",
            "rest_day_strategy": "周一休息",
            "disabled_workout_types": ["I"],
            "double_run_policy": "cautious",
            "long_run_strategy": "长距离不超过 30%",
            "injury_risk_policy": "疼痛时取消强度",
            "additional_notes": "更重视长期稳定",
        },
    )
    assert "跑者基本信息" in prompt
    assert "目标信息" in prompt
    assert "训练偏好/训练哲学" in prompt
    assert "当前用户保存的 AI 教练偏好配置" in prompt
    assert "卡诺瓦专项" in prompt
    assert "疼痛时取消强度" in prompt
    assert "二四日结构" in prompt
    assert "眉山东坡半马" in prompt


def test_build_prompt_keeps_system_and_user_parts() -> None:
    prompt = build_prompt(make_request())
    assert "你是 GaitLogic Planner 的 AI 跑步训练计划草稿生成器" in prompt
    assert "原始用户输入 JSON" in prompt
