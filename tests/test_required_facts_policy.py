from datetime import datetime
from zoneinfo import ZoneInfo

from server.agent.enums import AgentIntent
from server.agent.required_facts_policy import resolve_required_facts_policy


NOW = datetime(2026, 10, 26, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def resolve(intent: AgentIntent, message: str = "synthetic request"):
    return resolve_required_facts_policy(intent=intent, message=message, current_time=NOW)


def test_capability_and_casual_requests_do_not_read_personal_facts_or_use_rag() -> None:
    for intent in (AgentIntent.CASUAL_CONVERSATION, AgentIntent.COACH_CAPABILITY_QUERY):
        policy = resolve(intent)
        assert policy.required_fact_set == ()
        assert policy.tool_preloads == ()
        assert policy.requires_knowledge_retrieval is False


def test_personal_analysis_requires_bounded_runner_facts_before_generation_without_rag() -> None:
    policy = resolve(AgentIntent.PERSONAL_TRAINING_ANALYSIS)
    assert policy.required_fact_set == (
        "runner_state", "runner_state_history", "recent_training", "current_cycle", "today_workout", "data_quality"
    )
    assert [name for name, _arguments in policy.tool_preloads] == [
        "get_runner_state", "get_runner_state_history", "get_recent_training",
        "get_current_training_cycle", "get_today_workout", "get_training_data_quality",
    ]
    assert policy.requires_knowledge_retrieval is False


def test_current_month_uses_calendar_boundaries_instead_of_rolling_28_days() -> None:
    policy = resolve(AgentIntent.PERSONAL_TRAINING_ANALYSIS, "读取本月训练并分析")
    recent = dict(policy.tool_preloads)["get_recent_training"]
    quality = dict(policy.tool_preloads)["get_training_data_quality"]
    assert recent["start_date"] == "2026-10-01"
    assert recent["end_date"] == "2026-10-26"
    assert recent["range_kind"] == "CURRENT_CALENDAR_MONTH"
    assert quality["window_days"] == 26


def test_race_discussion_reads_future_plan_without_writing_user_date_to_cycle_state() -> None:
    policy = resolve(AgentIntent.PERSONAL_TRAINING_ANALYSIS, "两周后有半马比赛，我该怎么调整")
    assert dict(policy.tool_preloads)["get_training_plan_window"] == {
        "start_date": "2026-10-26",
        "end_date": "2026-11-09",
        "prefer_confirmed_race_date": True,
    }


def test_general_knowledge_is_the_only_default_path_that_requires_rag() -> None:
    policy = resolve(AgentIntent.GENERAL_TRAINING_QUESTION)
    assert policy.required_fact_set == ("general_training_rules",)
    assert policy.requires_knowledge_retrieval is True


def test_targeted_fact_query_keeps_today_or_tomorrow_scope() -> None:
    tomorrow = resolve(AgentIntent.PERSONAL_TRAINING_FACT_QUERY, "\u660e\u5929\u8dd1\u4ec0\u4e48")
    assert tomorrow.tool_preloads == (("get_today_workout", {"target_date": "2026-10-27"}),)
    assert tomorrow.requires_knowledge_retrieval is False
