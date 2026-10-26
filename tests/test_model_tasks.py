from planner_core.config import Settings
from server.agent.enums import AgentIntent
from server.model_tasks import ModelTaskType, coach_intent_model_profile, task_model_profile


def settings(**updates) -> Settings:
    values = {
        "COACH_AGENT_MODEL": "deepseek-flash",
        "COACH_AGENT_THINKING_MODE": "enabled",
        "COACH_ANALYSIS_MODEL": "deepseek-flash",
        "PLAN_DESIGN_MODEL": "deepseek-v4-pro",
    }
    values.update(updates)
    return Settings(_env_file=None, **values)


def test_coach_profiles_are_server_owned_and_bound_to_intent() -> None:
    configured = settings()
    assert coach_intent_model_profile(configured, AgentIntent.CASUAL_CONVERSATION).profile_name == "chat_fast"
    assert coach_intent_model_profile(configured, AgentIntent.PERSONAL_TRAINING_FACT_QUERY).profile_name == "coach_facts"
    analysis = coach_intent_model_profile(configured, AgentIntent.PERSONAL_TRAINING_ANALYSIS)
    assert analysis.profile_name == "coach_analysis"
    assert analysis.thinking_enabled is True
    assert analysis.reasoning_effort == "high"
    assert (
        coach_intent_model_profile(configured, AgentIntent.PLAN_ADJUSTMENT_ANALYSIS).profile_name
        == "plan_reasoning"
    )


def test_fast_and_fact_profiles_never_enable_thinking() -> None:
    configured = settings()
    for task in (ModelTaskType.COACH_CHAT_FAST, ModelTaskType.COACH_FACT_QUERY):
        profile = task_model_profile(configured, task)
        assert profile.thinking_enabled is False
        assert profile.reasoning_effort is None


def test_plan_reasoning_is_deep_only_when_server_policy_allows_it() -> None:
    enabled = task_model_profile(settings(), ModelTaskType.PLAN_DESIGN)
    disabled = task_model_profile(
        settings(COACH_AGENT_THINKING_MODE="disabled"), ModelTaskType.PLAN_DESIGN
    )
    assert enabled.profile_name == "plan_reasoning"
    assert enabled.thinking_enabled is True
    assert disabled.thinking_enabled is False
