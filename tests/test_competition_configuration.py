from planner_core.config import Settings


def test_competition_configuration_defaults_are_disabled(monkeypatch):
    for key in (
        "COMPETITION_MODE", "ENABLE_EXPERIMENT_DASHBOARD", "ENABLE_AGENT_TRACE",
        "ENABLE_SURVEY_MODULE", "ENABLE_COMPETITION_DEMO_DATA",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.competition_mode is False
    assert settings.enable_experiment_dashboard is False
    assert settings.enable_agent_trace is False
    assert settings.enable_survey_module is False
    assert settings.enable_competition_demo_data is False
