from pathlib import Path

from planner_core.config import PROJECT_ENV_FILE, PROJECT_ROOT, Settings


def test_default_env_file_is_anchored_to_project_root():
    assert PROJECT_ROOT == Path(__file__).resolve().parents[1]
    assert PROJECT_ENV_FILE == PROJECT_ROOT / ".env"
    assert Path(Settings.model_config["env_file"]) == PROJECT_ENV_FILE


def test_explicit_env_file_disable_still_supports_isolated_tests():
    settings = Settings(_env_file=None)
    assert settings.mysql_host == "127.0.0.1"
