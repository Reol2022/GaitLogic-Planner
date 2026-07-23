from server.agent.prompts import COACH_AGENT_PROMPT_VERSION, build_coach_agent_system_prompt


def test_prompt_is_versioned_and_contains_safety_authority_rules() -> None:
    prompt = build_coach_agent_system_prompt()
    assert COACH_AGENT_PROMPT_VERSION in prompt
    assert "Never invent" in prompt
    assert "deterministic rule decisions" in prompt
    assert "medical diagnosis" in prompt
    assert "plan was changed" in prompt
    assert "UNKNOWN" in prompt
    assert "strict AgentModelOutput JSON schema" in prompt
    assert "Return exactly one valid JSON object." in prompt
    assert "response format is json" in prompt
    assert "Do not use Markdown code fences." in prompt
    assert "Do not include text before or after the JSON object." in prompt
    assert '"today_recommendation":null' in prompt
    assert "chain of thought" in prompt


def test_prompt_contains_no_credentials_or_user_data() -> None:
    lowered = build_coach_agent_system_prompt().lower()
    assert "sk-" not in lowered
    assert "bearer " not in lowered
    assert "@example" not in lowered
    assert "runner_id" not in lowered
