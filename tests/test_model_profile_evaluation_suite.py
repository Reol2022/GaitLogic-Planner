from server.agent.evaluation.model_profile_suite import synthetic_model_profile_cases


def test_synthetic_model_profile_suite_has_thirty_private_safe_cases() -> None:
    cases = synthetic_model_profile_cases()
    assert len(cases) == 30
    assert len({case.case_id for case in cases}) == 30
    assert {case.expected_profile for case in cases} == {
        "chat_fast",
        "coach_facts",
        "coach_analysis",
        "plan_reasoning",
    }
    assert all(not case.requires_rag for case in cases)
    assert all("user" not in case.case_id for case in cases)
