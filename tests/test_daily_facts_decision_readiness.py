from server.domain.decision_readiness import DecisionReadiness
from server.services.training_facts.daily_facts import _data_limited, _decision_readiness


def test_missing_recovery_fields_do_not_globally_block_today_decision() -> None:
    facts = {
        "recovery": {
            "sleep_hours": None,
            "leg_feel": None,
            "subjective_fatigue": None,
        },
        "recent_training": {
            "missing_data": ["duration_or_rpe", "recovery_checkins"],
        },
    }

    assert _data_limited(facts) is False
    assert _decision_readiness(facts) is DecisionReadiness.PARTIAL


def test_missing_training_logs_remain_a_core_today_blocker() -> None:
    facts = {"recent_training": {"missing_data": ["training_logs"]}}
    assert _data_limited(facts) is True
    assert _decision_readiness(facts) is DecisionReadiness.BLOCKED


def test_failed_load_collection_remains_a_core_today_blocker() -> None:
    facts = {"recent_training": {"core_data_unavailable": True}}
    assert _data_limited(facts) is True
    assert _decision_readiness(facts) is DecisionReadiness.BLOCKED


def test_complete_daily_facts_are_ready() -> None:
    assert _decision_readiness({"recent_training": {"missing_data": []}}) is DecisionReadiness.READY
